"""
Gemini tags each evidence entry: which topics it mentions, whether each is a
complaint or praise, whether it suggests a safety risk, and an optional detail
(e.g. "pista 12"). Only topics from rules.TOPICS are accepted.

Neutral answers ("bien", "normal") get no tags.
"""

import json
import os
import time

from evidence import rules as R

BATCH_SIZE = 25

PROMPT = """Eres un analista de un club de pádel en Madrid. Vas a etiquetar comentarios de
varias fuentes: encuestas de socios tras jugar, el registro de incidencias de recepción,
notas del personal y reseñas de Google.

Para cada entrada, indica qué temas menciona. Usa SOLO estos temas:
{topics}

Reglas:
- "polarity": "queja" si describe un problema, "elogio" si lo valora positivamente.
- Respuestas neutras o sin contenido ("bien", "normal", "-", "no") -> "tags": [].
- Un mismo comentario puede tener varios temas (p. ej. arena y aparcamiento).
- "safety": true SOLO si describe un riesgo físico real (resbalar, caída, lesión,
  puerta o red rota que puede golpear, cristal roto, electricidad). Si no, false.
- "detail": un dato concreto si lo hay (p. ej. "pista 12", "vestuario de hombres"), si no null.
- No inventes nada que no esté en el texto. Si un tema no encaja, usa "otro".
- Un registro de recepción sobre un objeto olvidado -> tema "objetos_perdidos".
- Grupos de clase llenos, listas de espera o gente que pide plaza y no la hay ->
  tema "plazas_clases" con polaridad "queja" (es una demanda que el club no cubre),
  NO un elogio de "clases_profesores". Elogio de profesores o de una clase concreta
  -> "clases_profesores".

Devuelve SOLO un JSON (sin ``` ni texto extra) con esta forma:
[{{"id": "ENC-001", "tags": [{{"topic": "aparcamiento", "polarity": "queja", "safety": false, "detail": null}}]}}]

Entradas:
{entries}
"""


def _gemini_call(prompt: str) -> str:
    """Default LLM call: agents/llm.py (retries + tracking) when available,
    otherwise the google-genai SDK directly (e.g. in the standalone test script)."""
    config = {"response_mime_type": "application/json", "temperature": 0}
    try:
        from llm import generate
    except ImportError:
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents"))
        try:
            from llm import generate
        except ImportError:
            generate = None
    if generate:
        return generate(prompt, agent="insights_tagging", model=model_name(), config=config)
    from google import genai  # pip install google-genai
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Falta GEMINI_API_KEY (o GOOGLE_API_KEY) en el .env")
    client = genai.Client(api_key=api_key)
    return client.models.generate_content(model=model_name(), contents=prompt, config=config).text


def _clean_json(text: str):
    text = text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(text)


def _validate(raw_items, valid_ids):
    rows = []
    for entry in raw_items:
        eid = entry.get("id")
        if eid not in valid_ids:
            continue
        seen = set()
        for t in entry.get("tags", []) or []:
            topic = t.get("topic") if t.get("topic") in R.TOPICS else "otro"
            polarity = t.get("polarity") if t.get("polarity") in ("queja", "elogio") else None
            if polarity is None or (topic, polarity) in seen:
                continue
            seen.add((topic, polarity))
            rows.append({"evidence_id": eid, "topic": topic, "polarity": polarity,
                         "safety": bool(t.get("safety")) and polarity == "queja",
                         "detail": t.get("detail") or None})
    return rows


def tag_items(items, llm_call=None, retries=3):
    """
    items: list of EvidenceItem (text in memory).
    Returns a list of tag rows. Entries with no tags simply produce no rows.
    """
    llm_call = llm_call or _gemini_call
    topics = "\n".join(f"- {k}: {v['label']}" for k, v in R.TOPICS.items())
    rows = []
    for i in range(0, len(items), BATCH_SIZE):
        batch = items[i:i + BATCH_SIZE]
        entries = "\n\n".join(f"[{it.id}] ({it.source})\n{it.text}" for it in batch)
        prompt = PROMPT.format(topics=topics, entries=entries)
        last_error = None
        for attempt in range(retries):
            try:
                rows.extend(_validate(_clean_json(llm_call(prompt)), {it.id for it in batch}))
                last_error = None
                break
            except Exception as e:  # noqa: BLE001
                if type(e).__name__ == "GeminiUnavailable":
                    raise   # already retried inside llm.generate: show the friendly message
                last_error = e
                time.sleep(2 ** attempt)
        if last_error:
            raise RuntimeError(f"Gemini no pudo etiquetar {batch[0].id}–{batch[-1].id}: {last_error}")
    return rows


def model_name():
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
