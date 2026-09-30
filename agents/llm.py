"""
llm.py — the ONE place where the system talks to Gemini (Phase 3).

Every agent calls generate() instead of calling Gemini directly, so every
call gets the same production behaviour:
- Retries: up to 3 attempts, waiting 2 s, then 4 s, when Gemini is busy,
  slow or returns an error. Most "Gemini is busy" moments pass in seconds.
- A clear error: if all attempts fail, GeminiUnavailable is raised with a
  message in plain Spanish for the owner. Pages show it instead of a red
  technical error, and nothing already approved is lost (every decision is
  saved in Supabase at the moment it's made).
- Tracking: each call is logged to the llm_calls table (agent, model,
  seconds, tokens, attempts, ok/error, and an estimated cost in USD).
  Logging never breaks the app: if it fails, the call still works.

Prices live in .env, not in the code, because they change: set
GEMINI_PRICE_INPUT_USD_PER_M and GEMINI_PRICE_OUTPUT_USD_PER_M (US dollars
per million tokens, as Google publishes them). Without them, cost is left empty.
gemini-3.7-flash, Standard, paid tier (ai.google.dev/gemini-api/docs/pricing,
checked 30/09/2026): $0.75 input / $3.75 output through 31/12/2026, then
$1.50 / $7.50 from 01/01/2027 — update .env on that date. On the free tier
the real cost is $0; the figure shows what the paid tier would cost.
Output is billed INCLUDING thinking tokens, so both are counted as output.
"""

import os
import time

from dotenv import load_dotenv
from google import genai

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
MAX_ATTEMPTS = 3
FRIENDLY_ERROR = ("Gemini no responde ahora mismo. Inténtalo de nuevo en un minuto; "
                  "no se ha perdido nada de lo que ya habías guardado.")

_client = None
_supabase = None


class GeminiUnavailable(Exception):
    """All attempts failed. str(error) is the owner-facing message."""


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    return _client


def _get_supabase():
    global _supabase
    if _supabase is None:
        from supabase import create_client
        _supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    return _supabase


def _price(name: str):
    try:
        value = os.getenv(name)
        return float(value) if value else None
    except ValueError:
        return None


def _log(agent, model, seconds, input_tokens, output_tokens, attempts, status, error=None):
    """Best effort: a logging failure must never stop the agent."""
    try:
        cost = None
        p_in, p_out = _price("GEMINI_PRICE_INPUT_USD_PER_M"), _price("GEMINI_PRICE_OUTPUT_USD_PER_M")
        if p_in is not None and p_out is not None and input_tokens is not None:
            cost = round((input_tokens * p_in + (output_tokens or 0) * p_out) / 1_000_000, 6)
        _get_supabase().table("llm_calls").insert({
            "agent": agent, "model": model, "duration_ms": int(seconds * 1000),
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "cost_usd": cost, "attempts": attempts, "status": status,
            "error": (str(error)[:500] if error else None),
        }).execute()
    except Exception:  # noqa: BLE001
        pass


def generate(prompt: str, agent: str, model: str | None = None, config: dict | None = None) -> str:
    """Sends one prompt to Gemini with retries and tracking. Returns the text.
    agent: short name for the logs, e.g. "insights", "action_planning", "pala"."""
    model = model or MODEL
    start, last_error = time.time(), None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            kwargs = {"model": model, "contents": prompt}
            if config:
                kwargs["config"] = config
            response = _get_client().models.generate_content(**kwargs)
            text = response.text or ""
            usage = getattr(response, "usage_metadata", None)
            # Google bills output INCLUDING thinking tokens, so both count as output
            output = (getattr(usage, "candidates_token_count", None) or 0) + \
                     (getattr(usage, "thoughts_token_count", None) or 0)
            _log(agent, model, time.time() - start,
                 getattr(usage, "prompt_token_count", None),
                 output if usage is not None else None, attempt, "ok")
            return text
        except Exception as e:  # noqa: BLE001 - busy, timeout, quota, network…
            last_error = e
            if attempt < MAX_ATTEMPTS:
                time.sleep(2 ** attempt)   # 2 s, then 4 s
    _log(agent, model, time.time() - start, None, None, MAX_ATTEMPTS, "error", last_error)
    raise GeminiUnavailable(FRIENDLY_ERROR) from last_error
