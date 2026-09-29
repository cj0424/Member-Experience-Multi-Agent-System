"""
Insights Agent (Phase 3) — reads FOUR sources, not two:
post-session survey (ENC-), reception incident log (INC-), staff
observations (OBS-) and Google reviews (REV-).

The work is split so the numbers are exact and repeatable:
1. evidence/pipeline.py loads the week, saves it, and Gemini TAGS each
   entry (topic, complaint or praise, safety).
2. evidence/engine.py (plain Python) counts, applies the pattern rules
   (28-day window, 2+ dates, 3+ mentions or 2+ source types, slow rule),
   scores priority and confidence, and builds strengths / a vigilar / alerts.
   All numbers: evidence/rules.py · explained in docs/insights-pattern-rules.md
3. This agent asks Gemini only to NAME each pattern and explain in 1-2
   sentences what it means, from the real evidence. It can't add, drop or
   re-score patterns.

Memory: each pattern keeps its topic in Supabase, so a pattern found again
is matched to the one already registered by topic (not by wording).
"""

import json
import os
import re
import sys
from datetime import date

from dotenv import load_dotenv
from google import genai

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from evidence.pipeline import run as run_evidence  # noqa: E402

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "gemini-3.7-flash"

SOURCE_LABELS = {"survey": "encuesta", "incident": "incidencias",
                 "staff": "personal", "google": "Google"}
PREFIX_LABELS = {"ENC": "encuesta", "INC": "incidencias", "OBS": "personal", "REV": "Google"}


def _normalize(name: str) -> str:
    return re.sub(r"[^a-záéíóúñü0-9 ]", "", (name or "").lower()).strip()


def match_known(pattern: dict, known: list[dict]) -> dict | None:
    """Same topic = same pattern. Falls back to the name for older rows without a topic."""
    for k in known:
        if k.get("topic") and k["topic"] == pattern["topic"]:
            return k
    label = _normalize(pattern["label"])
    for k in known:
        if not k.get("topic") and _normalize(k.get("pattern_name")) == label:
            return k
    return None


def _evidence_lines(ids, texts):
    lines = []
    for i in ids:
        src = PREFIX_LABELS.get(i.split("-")[0], "")
        text = re.sub(r"\s+", " ", texts.get(i, "")).strip()
        lines.append(f"  - [{i}] ({src}) {text[:300]}")
    return "\n".join(lines)


def write_patterns(patterns: list[dict], texts: dict, registered_names: dict) -> dict:
    """Gemini writes a short name and "qué significa" for each pattern.
    Returns {topic: {"nombre": ..., "que_significa": ...}}."""
    blocks = []
    for p in patterns:
        fixed = registered_names.get(p["topic"])
        blocks.append(
            f"TEMA: {p['topic']} ({p['label']})\n"
            + (f"NOMBRE YA REGISTRADO (úsalo tal cual): {fixed}\n" if fixed else "")
            + (f"DETALLES: {', '.join(p['details'])}\n" if p.get("details") else "")
            + f"EVIDENCIA ({p['mentions']} menciones, {p['distinct_dates']} fechas distintas):\n"
            + _evidence_lines(p["evidence_ids"], texts)
            + (f"\nEN CONTRA:\n{_evidence_lines(p['contradicting_ids'], texts)}"
               if p.get("contradicting_ids") else "")
        )
    prompt = f"""Eres un analista de la experiencia de socios de un club de pádel en Madrid.
El sistema YA ha decidido, con reglas fijas, qué temas son patrones. Tu única tarea
es ponerle a cada uno un nombre claro y explicar qué significa, usando SOLO la
evidencia que aparece debajo.

Para cada tema:
- "nombre": 3 a 8 palabras, en español de España, que describan el problema
  concreto (por ejemplo "Aparcamiento lleno en el cambio de turno de tarde").
  Si hay un NOMBRE YA REGISTRADO, cópialo exactamente.
- "que_significa": 1 o 2 frases cortas: qué pasa, cuándo o dónde si la evidencia
  lo dice (pista, horario, vestuario), y qué fuentes lo confirman. Si hay evidencia
  EN CONTRA, menciónala en media frase. No inventes cifras, fechas ni causas.

Responde SOLO con un JSON (sin ``` ni texto extra):
[{{"topic": "...", "nombre": "...", "que_significa": "..."}}]

TEMAS:
{chr(10).join(blocks)}"""
    written = {}
    try:
        raw = client.models.generate_content(model=MODEL, contents=prompt).text
        raw = raw.strip().replace("```json", "").replace("```", "").strip()
        for x in json.loads(raw):
            if x.get("topic"):
                written[x["topic"]] = {"nombre": (x.get("nombre") or "").strip(),
                                       "que_significa": (x.get("que_significa") or "").strip()}
    except Exception:  # noqa: BLE001 - fall back to the topic label below
        pass
    return written


def _sources_text(source_types):
    return " + ".join(SOURCE_LABELS.get(s, s) for s in source_types)


def build_pattern_block(p, name, meaning, registro, known_id):
    reg = registro if not known_id else f"{registro} — #{known_id}"
    conf_icon = "🟢" if p["confidence"] == "Alta" else "🟡"
    lines = [
        f"🔍 PATRÓN — {name}",
        "🟢 ACTIVO",
        f"🔗 Registro: {reg}",
        f"⚡ Prioridad: {p['priority']} ({p['score']}/15 · gravedad {p['severity']}, alcance {p['reach']}, "
        f"frecuencia {p['frequency']}, actualidad {p['recency']})",
        f"📎 Evidencia: {p['mentions']} menciones en {p['distinct_dates']} fechas "
        f"({', '.join(p['evidence_ids'])}) — fuentes: {_sources_text(p['source_types'])}",
        f"{conf_icon} Confianza: {p['confidence']}",
        f"🧭 Qué significa: {meaning or p['label']}",
    ]
    if p.get("contradicting_ids"):
        lines.append(f"↔️ En contra: {', '.join(p['contradicting_ids'])}")
    if p["rule"] != "principal":
        lines.append("🐢 Detectado por la regla lenta: se repite en 3 semanas distintas en 90 días.")
    return "\n".join(lines)


def build_report(ev, blocks):
    ps, pe = date.fromisoformat(ev["period_start"]), date.fromisoformat(ev["period_end"])
    src = ev["sources"]
    out = [f"## Semana del {ps:%d/%m} al {pe:%d/%m/%Y}", "",
           "**Fuentes leídas:** "
           + " · ".join(f"{SOURCE_LABELS[k]} {v['read']}" + (" (error)" if v["status"] == "error" else "")
                        for k, v in src.items())
           + f" · reseñas de Google nuevas: {ev['google_new_reviews']}", ""]

    if ev["alerts"]:
        out.append("### ⚠️ Alertas de seguridad (avisar sin esperar)")
        out += [f"- **{a['label']}** — {', '.join(a['evidence_ids'])}" for a in ev["alerts"]]
        out.append("")

    out.append(f"### Patrones activos ({len(blocks)})")
    out += (["\n\n---\n\n".join(blocks)] if blocks
            else ["No hay evidencia suficiente para un patrón esta semana (semana tranquila)."])
    out.append("")

    if ev["strengths"]:
        out.append("### 💪 Fortalezas")
        out += [f"- **{s['label']}** — {s['mentions']} menciones ({', '.join(s['evidence_ids'])}) — "
                f"fuentes: {_sources_text(s['source_types'])}" for s in ev["strengths"]]
        out.append("")
    if ev["a_vigilar"]:
        out.append("### 👀 A vigilar (todavía no es un patrón)")
        out += [f"- **{w['label']}** — {w['mentions']} mención(es): {', '.join(w['evidence_ids'])}"
                for w in ev["a_vigilar"]]
        out.append("")
    out.append("*Límites: la encuesta solo recoge a quien responde el QR; las reseñas de Google son "
               "pocas y se leen en directo (máximo 5 por consulta); el registro de incidencias y las "
               "notas del personal dependen de que se rellenen. Por eso un patrón necesita repetirse en "
               "días distintos y, si es posible, en más de una fuente.*")
    return "\n".join(out)


def run_insights_agent(week_dir: str, period_start: date, known: list[dict] | None = None) -> dict:
    """
    Returns {"text": report for the owner, "patterns": one dict per active pattern
    (nombre, texto, registro, id, and the fields saved with the pattern),
    "evidence": the engine result (strengths, a_vigilar, alerts, sources...)}.
    """
    known = known or []
    ev = run_evidence(week_dir, period_start, use_db=True)
    texts = ev.get("texts", {})

    matches = {p["topic"]: match_known(p, known) for p in ev["patterns"]}
    registered = {t: k["pattern_name"] for t, k in matches.items() if k}
    written = write_patterns(ev["patterns"], texts, registered) if ev["patterns"] else {}

    patterns, blocks = [], []
    for p in ev["patterns"]:
        k = matches[p["topic"]]
        w = written.get(p["topic"], {})
        name = k["pattern_name"] if k else (w.get("nombre") or p["label"])
        registro = ("REAPARECE" if k and k.get("status") == "closed"
                    else "YA REGISTRADO" if k else "NUEVO")
        block = build_pattern_block(p, name, w.get("que_significa"), registro, k["id"] if k else None)
        blocks.append(block)
        patterns.append({
            "nombre": name, "texto": block, "registro": registro, "id": k["id"] if k else None,
            "meta": {
                "topic": p["topic"], "priority": p["priority"], "priority_score": p["score"],
                "confidence": p["confidence"], "evidence_ids": ", ".join(p["evidence_ids"]),
                "detected_period_end": ev["period_end"],
            },
        })

    evidence = {k: v for k, v in ev.items() if k != "texts"}
    return {"text": build_report(ev, blocks), "patterns": patterns, "evidence": evidence}


# No terminal runner here on purpose: running Insights saves the week to Supabase.
# To test the evidence step without writing anything, use:
#   python scripts/run_evidence_pipeline.py --week-dir data/week1 --period-start 2026-09-14 --no-db
