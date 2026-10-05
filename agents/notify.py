"""
notify.py — delivers the weekly summary (Phase 3).

Channel chosen in .env with NOTIFY_CHANNEL:
- telegram (the demo channel): a Telegram bot sends the message to one chat.
      TELEGRAM_BOT_TOKEN   from @BotFather
      TELEGRAM_CHAT_ID     find it with: python scripts/telegram_chat_id.py
- whatsapp (the production channel for a Spanish club): WhatsApp Cloud API.
      WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_TO, WHATSAPP_API_VERSION (optional)
      Note: a business can only START a WhatsApp conversation with an approved
      template; plain text is delivered only within 24 h of the recipient writing.
Without a configured channel nothing is sent: the message is still saved in
Supabase (notifications) and shown on the Dashboard.

Formatting: Pala writes the summary with **bold** (the only formatting it uses).
Each channel gets it in its own format, so the phone shows real bold instead of
asterisks:
- Telegram: HTML mode (<b>bold</b>). If Telegram ever rejects the formatting,
  the message is sent again as plain text, so it's never lost.
- WhatsApp: *bold* (WhatsApp's own syntax).
- Dashboard / saved copy: plain text (plain_text), without symbols.
"""

import html
import json
import os
import re
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()

MAX_CHARS = 3900          # Telegram's limit is 4096; leave room for the bold tags
BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)


def channel() -> str:
    return (os.getenv("NOTIFY_CHANNEL") or "telegram").strip().lower()


def configured() -> bool:
    if channel() == "whatsapp":
        return all(os.getenv(k) for k in ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_TO"))
    return all(os.getenv(k) for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"))


# ---------------------------------------------------------------------------
# One message, three formats
# ---------------------------------------------------------------------------

def plain_text(text: str) -> str:
    """Without any formatting symbols: for the Dashboard and as a fallback."""
    return BOLD.sub(r"\1", text or "").replace("**", "")


def to_telegram_html(text: str) -> str:
    """**bold** → <b>bold</b>. Everything else is escaped, so characters like
    < or & in the text can't break Telegram's formatting."""
    safe = html.escape(text or "", quote=False)
    safe = BOLD.sub(r"<b>\1</b>", safe)
    return safe.replace("**", "")


def to_whatsapp(text: str) -> str:
    """**bold** → *bold* (WhatsApp's bold)."""
    return BOLD.sub(r"*\1*", text or "").replace("**", "")


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

def _post(url: str, payload: dict, headers: dict | None = None) -> tuple[bool, str | None]:
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                     headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return 200 <= response.status < 300, None
    except urllib.error.HTTPError as e:
        return False, f"{e.code}: {e.read().decode(errors='ignore')[:300]}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def send(text: str) -> tuple[bool, str | None]:
    """Sends through the configured channel. Returns (sent, error_message)."""
    if not configured():
        return False, f"{channel()} no está configurado (.env)"
    text = (text or "")[:MAX_CHARS]

    if channel() == "whatsapp":
        version = os.getenv("WHATSAPP_API_VERSION", "v23.0")
        ok, err = _post(
            f"https://graph.facebook.com/{version}/{os.getenv('WHATSAPP_PHONE_NUMBER_ID')}/messages",
            {"messaging_product": "whatsapp", "to": os.getenv("WHATSAPP_TO"),
             "type": "text", "text": {"preview_url": False, "body": to_whatsapp(text)}},
            {"Authorization": f"Bearer {os.getenv('WHATSAPP_TOKEN')}"})
        return ok, (f"WhatsApp {err}" if err else None)

    url = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage"
    chat = os.getenv("TELEGRAM_CHAT_ID")
    ok, err = _post(url, {"chat_id": chat, "text": to_telegram_html(text),
                          "parse_mode": "HTML", "disable_web_page_preview": True})
    if not ok and err and err.startswith("400"):
        # Telegram couldn't read the formatting: send it as plain text instead
        ok, err = _post(url, {"chat_id": chat, "text": plain_text(text),
                              "disable_web_page_preview": True})
    return ok, (f"Telegram {err}" if err else None)
