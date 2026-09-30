"""
faq_agent.py — Pala, "tu asistente del club" (opened from the floating 💬 Ayuda button).

Not a manual: each page already explains itself ("¿Qué pasa en esta
página?"). Pala does what no single page does — it reads ALL the club's
patterns at once and answers in a few lines:
- 🧭 what to do now, in priority order, and where to do it;
- 📊 how the club is doing (resolved / progressing / pending);
- 🔁 what to prepare for the next check-ins, and when they're due;
- 📅 tasks for the Monday team meeting, one owner each;
- 🚫 every idea already rejected, so nobody proposes it again;
- 🔍 what happened with one pattern, in 3 lines.

Grounded ONLY on real data: Supabase (patterns + pattern_history,
including what the owner said at each check-in), the journey counts, and
the club profile (roles, Monday meeting, tú/usted). Read-only: it never
approves, changes or sends anything.

Phase 3: Pala also sees the patterns detected and waiting for their
recommendation (pending_recommendations), each pattern's priority, what
the four sources said automatically at the last check-in (kept apart from
what the owner said), and tells rejected ideas from postponed ones.
"""

import os
import re
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from google import genai

import db
from rag import load_club_profile

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

CHECKIN_EVERY_DAYS = 14

# Only used to point the owner to the right place — not to explain pages.
PAGE_MAP = """- "Resumen": tarjetas de "Tu siguiente paso" y el estado de cada patrón.
- "1 · Detectar": botón "Ejecutar análisis" (detecta los patrones de la semana); los nuevos esperan en la lista
  "Pendientes de recomendación" → en su tarjeta, "Generar recomendación →" (Aprobar / Pedir cambios /
  Descartar, o "Decidir más tarde"). Se revisan uno a uno.
- "2 · Preparar": tarjeta del patrón → botón "Generar kit →"; kits aprobados → "Ver kit →" (trackers en Excel).
- "3 · Seguir": tarjeta del patrón → botón "Revisar →" (se indica si se hizo, con qué prueba, y si mejoró).
- "4 · Historial": tarjeta del patrón → "Ver historia →" (historia completa y lo descartado)."""


def _one_line(text: str, limit: int | None = 220) -> str:
    text = re.sub(r"[#*>`]", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    if limit and len(text) > limit:
        return text[:limit] + "…"
    return text


def _parse_date(iso) -> datetime | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _fmt(dt: datetime | None) -> str:
    return dt.strftime("%d/%m/%Y") if dt else "—"


def _checkin_conclusion(narrative: str) -> str:
    """The closing paragraph after 'Decisión:' if any, else the last step."""
    after, last_step, seen = [], "", False
    for line in (narrative or "").split("\n"):
        plain = re.sub(r"[#*]", "", line).strip()
        if not plain:
            continue
        if re.match(r"Decisi[oó]n\s*(final)?\s*:", plain, re.I):
            seen = True
            continue
        if seen:
            after.append(plain)
            continue
        m = re.match(r"Paso\s*\d\s*[:.-]\s*(.*)", plain, re.I)
        if m and m.group(1):
            last_step = m.group(1)
    return _one_line(" ".join(after) if after else last_step, 300)


def club_digest() -> str:
    """A compact, factual snapshot of every pattern — Pala's only source
    about the club's situation."""
    lines = []
    for p in db.get_all_patterns():
        history = db.get_history(p["id"])
        attempt = p.get("attempt") or 1
        checkins = [e for e in history if e.get("event_type") == "check_in"]
        current = [e for e in checkins if (e.get("attempt") or 1) == attempt]
        stage = db.pattern_stage(p, len(current))
        last = checkins[-1] if checkins else None
        last_date = _parse_date(last.get("created_at")) if last else None

        parts = [f"#{p['id']} {p['pattern_name']}", f"fase: {stage}", f"intento {attempt}"]
        if p.get("priority"):
            parts.append(f"prioridad {p['priority']}")
        if p.get("last_decision"):
            parts.append(f"última decisión: {p['last_decision']}")
        block = " | ".join(parts)

        # When the next check-in is due
        if stage in ("Kit", "Seguimiento"):
            if last_date:
                due = last_date + timedelta(days=CHECKIN_EVERY_DAYS)
                block += f"\n   Último seguimiento: {_fmt(last_date)} · próximo recomendado: hacia el {_fmt(due)}"
            else:
                kit_events = [e for e in history if e.get("event_type") == "kit_aprobado"]
                kit_date = _parse_date(kit_events[-1].get("created_at")) if kit_events else None
                if kit_date:
                    due = kit_date + timedelta(days=CHECKIN_EVERY_DAYS)
                    block += (f"\n   Kit aprobado el {_fmt(kit_date)} · sin seguimientos aún · "
                              f"primer seguimiento recomendado: hacia el {_fmt(due)}")
                else:
                    block += "\n   Sin seguimientos aún"

        # The most up-to-date facts: what the owner said at the last check-in. Since
        # Phase 3 the check-in also stores what the four sources said automatically;
        # it's shown apart, so Pala never presents it as the owner's own words.
        if last:
            summary = last.get("evidence_summary") or ""
            owner_part, _, sources_part = summary.partition("\nFuentes desde la detección:")
            if owner_part.strip():
                block += ("\n   Lo que indicó el propietario en el último seguimiento (lo más actual): "
                          f"{_one_line(owner_part, 500)}")
            if sources_part.strip():
                block += ("\n   Lo que dijeron las fuentes en ese seguimiento (automático: encuesta, "
                          f"incidencias, personal, Google): {_one_line(sources_part, 400)}")
            block += f"\n   Conclusión del último seguimiento: {_checkin_conclusion(last.get('narrative'))}"

        if p.get("approved_action") and p.get("status") != "discarded":
            # The plan's own text (not just its titles), so conditions like
            # "solo si el fallo es general" reach Pala
            block += f"\n   Plan aprobado (texto): {_one_line(p['approved_action'], 600)}"
        if p.get("execution_kit") and p.get("status") != "discarded":
            # The approved kit is the latest word on HOW it's done (the owner may have
            # changed details at the kit stage, e.g. frequency or who checks)
            kit = re.sub(r"===TRACKER_SPEC===.*?(===FIN_TRACKER_SPEC===|$)", "", p["execution_kit"], flags=re.S)
            block += f"\n   Kit aprobado (lo más reciente sobre cómo se hace): {_one_line(kit, 900)}"
        if p.get("status") == "open" and p.get("verification_method"):
            block += (f"\n   Cómo verificar (del kit original; si ya hubo seguimientos, manda lo "
                      f"último que se indicó): {_one_line(p['verification_method'], 220)}")
        if p.get("rejected_ideas"):
            # Never cut: a partial list would make the owner think an idea wasn't rejected.
            # Each line says "Descartado:" or "Pospuesto:" (postponed ideas can come back later).
            block += ("\n   Ideas descartadas o pospuestas (lista completa): "
                      f"{_one_line(p['rejected_ideas'], None)}")
        lines.append(block)
    return "\n".join(lines) or "Todavía no hay patrones registrados."


def pending_digest() -> str:
    """Patterns detected by the analysis and waiting for the owner to
    generate their recommendation (Detectar → "Generar recomendación →")."""
    try:
        waiting = db.get_pending_recommendations()
    except Exception:
        return "No disponible."
    lines = []
    for r in waiting:
        meta = r.get("meta") or {}
        ids = [i.strip() for i in (meta.get("evidence_ids") or "").split(",") if i.strip()]
        parts = [r["name"], f"prioridad {meta.get('priority') or '—'}",
                 f"confianza {meta.get('confidence') or '—'}", f"{len(ids)} mención(es)",
                 f"detectado el {_fmt(_parse_date(r.get('created_at')))}"]
        if r.get("kind") == "reaparece":
            parts.append("vuelve a aparecer (se había cerrado)")
        lines.append("- " + " | ".join(parts))
    return "\n".join(lines) or "Ninguno."


def build_prompt(question: str, history: list[dict], digest: str, counts: dict, club_profile: str,
                 pending: str = "Ninguno.") -> str:
    past = "\n".join(
        f"{'Propietario' if m['role'] == 'user' else 'Pala'}: {m['content']}"
        for m in history[-6:]
    ) or "Ninguna."
    days = counts.get("days_since_analysis")
    today = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    return f"""Te llamas Pala y eres el asistente del propietario de un club de pádel, dentro
de una app que detecta problemas en las opiniones de los socios, propone
planes, prepara kits de ejecución y hace seguimiento de los resultados.

Tu valor: ves TODOS los patrones a la vez y resumes, para que el propietario
no tenga que revisar página por página. No expliques cómo funciona cada
página (eso ya lo explica la propia app): responde con datos reales y dile
adónde ir y por qué.

QUÉ DATOS MANDAN:
- Lo que indicó el propietario en el último seguimiento es lo más actual
  (por ejemplo, "esperamos la respuesta de Playtomic" o "el clinic es el
  17/10"). Úsalo antes que cualquier otra cosa.
- Si un patrón ya tuvo seguimientos, basa lo siguiente en su último
  seguimiento, no en el "Cómo verificar" original del kit (que puede
  estar desfasado, por ejemplo si un evento ya pasó).
- Las fechas "recomendadas" son solo un cálculo (+14 días). Si lo que
  indicó el propietario muestra que la acción ocurre más tarde (por
  ejemplo, un clinic el 17/10) o depende de algo pendiente (por ejemplo,
  una respuesta de Playtomic), el seguimiento toca DESPUÉS de eso: di esa
  fecha o esa condición, nunca la fecha calculada.

CÓMO RESPONDER:
- Empieza por la respuesta, en una frase. Nada de introducciones.
- Qué hacer ahora: lista numerada de 1 a 5 acciones, por prioridad:
  1) patrones ESCALADOS; 2) FLAG con algo concreto que resolver;
  3) seguimientos que ya tocan (fecha recomendada pasada o hoy);
  4) patrones detectados que esperan su recomendación (empieza por el de
     prioridad más alta; se revisan uno a uno en "1 · Detectar");
  5) planes esperando su kit; 6) análisis si hace 7+ días del último.
  Si hay más de 5, quédate con las 5 primeras.
  Cada acción en una línea corta: qué hacer y, si hace falta, un
  "porque…" breve.
- Distingue dónde se hace cada cosa. Si la acción es EN EL CLUB (llamar a
  Playtomic, cubrir una plaza, revisar una pista), dilo así y no mandes a
  ninguna página. Nombra una página de la app (con su botón) solo cuando
  el siguiente paso se hace allí, y di cuándo: por ejemplo, "cuando
  Playtomic responda, regístralo en 3 · Seguir → Revisar →".
- Cómo va el club: tres líneas — Resuelto / Avanzando / Pendiente. En
  Pendiente, di el motivo de cada patrón: si espera algo concreto (por
  ejemplo, una respuesta de Playtomic) o si simplemente aún no toca.
- Próximos seguimientos: por cada patrón, cuándo toca (fecha recomendada
  o la condición de la que depende) y qué prueba reunir antes.
- Reunión del lunes: tareas concretas, cada una con UN solo responsable
  (un rol del PERFIL DEL CLUB, nunca "X o Y") y un plazo. Solo tareas que
  salgan de los datos.
- Ideas descartadas: todas, agrupadas por patrón, una línea por idea
  con su motivo: "idea (motivo: …)". Nómbrala tan exacta como se
  descartó (por ejemplo, "solo el aviso en las reservas", no "el aviso"),
  para no confundirla con algo que sí está en el plan aprobado.
  Distingue las DESCARTADAS de las POSPUESTAS: una idea pospuesta ("más
  adelante", "en primavera", "solo si no basta") no está rechazada; dilo
  así y, si su condición ya se cumple, puedes recordarla.
- Si el plan aprobado y el kit aprobado dicen cosas distintas sobre cómo se
  hace (frecuencia, quién, cuándo, qué se comprueba), manda el KIT: es lo
  más reciente y lo que decidió el propietario al preparar la ejecución.
- Si una parte del plan aprobado es condicional ("si…", "solo si…", "si no
  basta…", "cuando…"), dilo así ("si la revisión no basta, pedir
  presupuesto a un electricista"). Nunca la presentes como un paso seguro.
- Lo que dijeron las fuentes en un seguimiento es automático (socios,
  personal, Google); lo que indicó el propietario es lo suyo. No los
  mezcles ni atribuyas uno al otro.
- Un patrón concreto: su historia en 3 líneas (qué se detectó, qué se hizo,
  cómo va, incluido lo que indicó el propietario) y, para más detalle,
  "4 · Historial" → su tarjeta.
- Máximo unas 8 líneas. Pon en **negrita** solo los nombres de los patrones.
- Usa SOLO los datos de abajo. Si algo no está, dilo. No inventes cifras,
  fechas ni resultados. Nunca digas que has hecho o cambiado algo: solo
  informas y orientas.
- Si la pregunta no tiene que ver con el club o la app, dilo con amabilidad
  y sugiere una o dos preguntas que sí puedes responder.

CÓMO ESCRIBIR:
- Español de España, claro y cercano, con el tratamiento que indica el
  PERFIL DEL CLUB (tú o usted). Frases cortas.
- Lenguaje de la calle, no administrativo ni técnico. Por ejemplo:
  "pruebas" (no "evidencias"), "confirmar que se ha hecho" (no "certificar
  la ejecución"), "valorar si funciona" (no "desbloquear la evaluación"),
  "la hoja de inscripciones firmada" (no "validación firmada"),
  "indicado" o "comentado" (no "reportado").

HOY: {today}

DÓNDE ESTÁ CADA COSA (para orientar, no para explicar):
{PAGE_MAP}

SITUACIÓN ACTUAL:
- Último análisis de opiniones: {'nunca' if days is None else f'hace {days} día(s)'}
- Planes esperando su kit: {counts.get('pending_kit', 0)}
- Patrones que toca revisar: {counts.get('due_checkins', 0)}
- Patrones escalados: {counts.get('escalated', 0)}
- Patrones detectados esperando su recomendación: {counts.get('pending_plan', 0)}

PATRONES DETECTADOS QUE ESPERAN SU RECOMENDACIÓN (aún sin plan):
{pending}

PATRONES DEL CLUB (datos reales):
{digest}

PERFIL DEL CLUB (roles, reunión semanal, tratamiento):
{club_profile}

CONVERSACIÓN RECIENTE:
{past}

PREGUNTA:
{question}

Responde ahora."""


def run_faq_agent(question: str, history: list[dict] | None = None) -> str:
    try:
        counts = db.get_journey_counts()
    except Exception:
        counts = {}
    prompt = build_prompt(question, history or [], club_digest(), counts, load_club_profile(),
                          pending=pending_digest())
    response = client.models.generate_content(model="gemini-3.7-flash", contents=prompt)
    return response.text


if __name__ == "__main__":
    print(run_faq_agent("¿Qué hago ahora?"))
