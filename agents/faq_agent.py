"""
faq_agent.py — Pala, "tu asistente del club" (opened from the floating 💬 Ayuda button).

Not a manual: each page already explains itself ("¿Qué pasa en esta
página?"). Pala does what no single page does — it reads ALL the club's
patterns at once and answers in a few lines:
- 🧭 what to do now, in priority order, and where to do it;
- 📊 how the club is doing: resolved / working / pending / satisfaction,
  including whether the fixes are working (the club's impact figures);
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

Impact: Pala also receives the club's impact figures, already calculated in
plain Python by agents/impact.py (time to resolution, fixes that worked,
complaint change, satisfaction). Pala never calculates them itself: it only
explains them, with their limits (small sample, simulated data, open
patterns not counted yet).
"""

import re
from datetime import datetime, timedelta, timezone

import db
from rag import load_club_profile
from llm import generate, GeminiUnavailable

CHECKIN_EVERY_DAYS = 14

# Only used to point the owner to the right place — not to explain pages.
PAGE_MAP = """- "Resumen": tarjetas de "Tu siguiente paso" y el estado de cada patrón.
- "1 · Detectar": botón "Ejecutar análisis" (detecta los patrones de la semana); los nuevos esperan en la lista
  "Pendientes de recomendación" → en su tarjeta, "Generar recomendación →" (Aprobar / Pedir cambios /
  Descartar, o "Decidir más tarde"). Se revisan uno a uno.
- "2 · Preparar": tarjeta del patrón → botón "Generar kit →"; kits aprobados → "Ver kit →" (trackers en Excel).
- "3 · Seguir": tarjeta del patrón → botón "Revisar →" (se indica si se hizo, con qué prueba, y si mejoró).
- "4 · Historial e impacto": vista "📊 Impacto del club" (las cifras de resultados, los casos cerrados y la
  satisfacción semana a semana) y vista "📈 Historia de cada patrón" → tarjeta del patrón → "Ver historia →"
  (historia completa y lo descartado)."""


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
        score = meta.get("priority_score")
        parts = [r["name"], f"prioridad {meta.get('priority') or '—'}" + (f" ({score}/15)" if score else ""),
                 f"confianza {meta.get('confidence') or '—'}", f"{len(ids)} mención(es)",
                 f"detectado el {_fmt(_parse_date(r.get('created_at')))}"]
        if r.get("kind") == "reaparece":
            parts.append("vuelve a aparecer (se había cerrado)")
        lines.append("- " + " | ".join(parts))
    return "\n".join(lines) or "Ninguno."


def impact_digest() -> str:
    """The club's impact figures, already calculated by agents/impact.py
    (plain Python). Pala only explains them; it never recalculates."""
    try:
        import impact
        return impact.impact_text()
    except Exception:  # noqa: BLE001 - Pala still answers everything else
        return "No disponible en este momento."


def build_prompt(question: str, history: list[dict], digest: str, counts: dict, club_profile: str,
                 pending: str = "Ninguno.", impact_figures: str = "No disponible en este momento.") -> str:
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
- Qué hacer ahora: una frase corta y debajo una lista numerada de 1 a 6
  acciones, por prioridad. Formato de cada acción, en una línea:
  "1. 🏟️ **Nombre del patrón**: qué hacer, con su dato clave en negrita
  (por ejemplo, "a las **15:15**"), porque…" si se hace EN EL CLUB, o
  "1. 📱 **Nombre del patrón**: qué hacer en **qué página**" si se hace en
  la app. Orden de prioridad:
  1) patrones ESCALADOS; 2) FLAG con algo concreto que resolver;
  3) AJUSTES que propuso el último seguimiento (decisión CONTINUAR con un
     cambio concreto: mover una tarea de día, reparar un foco…). Son
     tareas EN EL CLUB: di cuál y para qué patrón;
  4) seguimientos que ya tocan (fecha recomendada pasada o hoy);
  5) patrones detectados que esperan su recomendación (empieza por el de
     mayor puntuación de prioridad; se revisan uno a uno en "1 · Detectar");
  6) planes esperando su kit; 7) análisis si hace 7+ días del último.
  Si hay más de 6, quédate con las 6 primeras.
- Si un seguimiento dice que aún falta tiempo porque depende de algo
  externo (por ejemplo, la respuesta de Playtomic), añade después de la
  lista una línea aparte "⏳ **Esperando:** …" y, si ya ha pasado una
  semana, sugiere reclamarlo.
  Cada acción en una línea corta: qué hacer y, si hace falta, un
  "porque…" breve.
- Distingue dónde se hace cada cosa. Si la acción es EN EL CLUB (llamar a
  Playtomic, cubrir una plaza, revisar una pista), dilo así y no mandes a
  ninguna página. Nombra una página de la app (con su botón) solo cuando
  el siguiente paso se hace allí, y di cuándo: por ejemplo, "cuando
  Playtomic responda, regístralo en 3 · Seguir → Revisar →".
- ¿Cómo va el club? (y cualquier pregunta sobre resultados, impacto o si
  los arreglos funcionan): responde SIEMPRE con una frase corta de
  respuesta y debajo esta lista de cuatro puntos, cada uno en su propia
  línea, empezando por "- ", en este orden y con estas etiquetas exactas:
  - ✅ **Resuelto:** cuántos casos se cerraron, con su nombre corto entre
    paréntesis (por ejemplo, "luces fuera de las pistas y pista 12"),
    cuántos con el primer plan y cuánto se tarda normalmente (pasa los
    días a semanas: 21 días = unas 3 semanas; di "normalmente", nunca
    "de media").
  - 📉 **Funcionando:** cómo cambiaron las quejas en los casos cerrados
    ("de 3 a 1") y, si IMPACTO DEL CLUB trae una "Comparación", lo que
    dice en pocas palabras ("y no en los abiertos, así que apunta a los
    arreglos").
  - ⏳ **Pendiente:** cuántos patrones siguen abiertos, repartidos en
    grupos según PATRONES DEL CLUB (por ejemplo, "2 avanzan con un
    ajuste, 2 esperan algo externo y 2 aún no tienen seguimiento"; cada
    patrón abierto en un solo grupo, y que los grupos sumen el total), y
    cómo van sus quejas (la cifra "en seguimiento", aunque no sea buena),
    nombrando solo el patrón o los dos patrones que más la explican, con
    su motivo en pocas palabras ("esperando a Playtomic"). Las fechas de
    los próximos seguimientos no van aquí: son de otra pregunta.
  - ⭐ **Satisfacción:** el % de respuestas positivas de la última semana
    y, si la muestra es pequeña, "es una primera señal".
  Cada punto, una o dos frases cortas como mucho, con su cifra clave en
  negrita (por ejemplo, "**2 casos**", "**de 3 a 1**", "**6 patrones**",
  "**75%**"). Termina con una línea aparte: "Más
  detalle en 4 · Historial e impacto."
  Usa SOLO las cifras de IMPACTO DEL CLUB, tal cual, sin recalcularlas.
  Las quejas, en números ("de 3 a 1"), nunca en porcentaje. No uses
  abreviaturas como "sem." ni términos técnicos como "mediana" o
  "solidez". Nunca digas que un arreglo causó el cambio de la
  satisfacción: como mucho, que coinciden en el tiempo. Si una cifra no
  está, di "aún no hay datos" en ese punto.
- Próximos seguimientos: una frase corta y debajo una lista, ordenada por
  fecha (primero la más cercana; los que dependen de una condición, al
  final). Formato de cada punto, en una línea:
  "- 📅 **hacia el 14/10** · Nombre del patrón: qué prueba reunir antes" o
  "- 📅 **cuando responda Playtomic** · Nombre del patrón: qué prueba reunir".
- Reunión del lunes: una frase corta y debajo una lista de tareas
  concretas, cada una con UN solo responsable (un rol del PERFIL DEL CLUB,
  nunca "X o Y") y un plazo. Formato de cada punto, en una línea:
  "- 👤 **Rol**: qué hacer (Nombre del patrón) · ⏰ **plazo**".
  Solo tareas que salgan de los datos.
- Ideas descartadas: todas, agrupadas por patrón. Para cada patrón, una
  línea "🚫 **Nombre del patrón**" y debajo un punto por idea:
  "- idea (motivo: …)"; si está pospuesta, "- ⏸️ idea (**pospuesta**: …)". Nómbrala tan exacta como se
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
- Un patrón concreto: una frase corta y su historia en tres puntos:
  "- 🔍 **Detectado:** cuándo y con qué pruebas",
  "- 📝 **Qué se hizo:** el plan y el kit",
  "- 🔁 **Cómo va:** el último seguimiento, incluido lo que indicó el
  propietario", con el dato clave de cada punto en negrita. Para más
  detalle: "4 · Historial e impacto" → "📈 Historia de cada patrón".
- ESTILO DE TODAS LAS RESPUESTAS (también las preguntas escritas a mano):
  empieza con una frase corta que responda; debajo, una línea por idea.
  Cada línea empieza con un icono y una etiqueta en negrita (el patrón,
  la persona, la fecha o el tema), y lleva en negrita UN dato clave (una
  cifra, una hora, un plazo). Como mucho DOS partes en negrita por línea,
  nunca frases enteras. Si la pregunta no encaja en ningún formato de
  arriba, sigue este mismo estilo. Máximo unas 8 líneas.
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
  "indicado" o "comentado" (no "reportado"), "la mediana" se puede decir
  como "lo normal" o "lo habitual".

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

IMPACTO DEL CLUB (cifras ya calculadas por la app; explícalas, no las recalcules):
{impact_figures}

PERFIL DEL CLUB (roles, reunión semanal, tratamiento):
{club_profile}

CONVERSACIÓN RECIENTE:
{past}

PREGUNTA:
{question}

Responde ahora."""


CLUB_LABELS = {"Resuelto": "✅", "Funcionando": "📉", "Pendiente": "⏳", "Satisfacción": "⭐"}


def _tidy_answer(text: str) -> str:
    """Makes sure the four labelled points of "¿Cómo va el club?" are each on
    their own line as a list (with their emoji), even if Gemini writes them
    as one paragraph, and that the closing pointer sits on its own line."""
    if not text or sum(f"**{l}:**" in text for l in CLUB_LABELS) < 2:
        return text
    for label, icon in CLUB_LABELS.items():
        text = re.sub(rf"\s*(?:-\s*)?(?:[✅📉⏳⭐]\s*)?\*\*{label}:\*\*",
                      f"\n- {icon} **{label}:**", text)
    text = re.sub(r"\s*(Más detalle en 4 · Historial)", r"\n\n\1", text)
    # a blank line before the list, so Markdown shows it as a list
    text = re.sub(r"^((?!- )[^\n]+)\n- ", r"\1\n\n- ", text.strip(), count=1)
    return text


def _blocked_without_login() -> bool:
    """Inside the Streamlit app, Pala only answers a logged-in user (it sees all
    the club's data). Scripts (e.g. the weekly run) are not in a browser session."""
    try:
        from streamlit.runtime import exists
        if not exists():
            return False
        from auth import is_authorized
        return not is_authorized()
    except Exception:  # noqa: BLE001
        return False


WEEKLY_QUESTION = (
    "Prepara el resumen del lunes para enviarlo por mensaje al propietario. Sin enlaces y sin "
    "otros símbolos de formato: SOLO se permite la negrita, escrita con dos asteriscos "
    "(**así**). Para que se lea de un vistazo, usa EXACTAMENTE este formato:\n"
    "- Primera línea: '📊 **Resumen de la semana**' y, en la línea siguiente, una frase corta con "
    "lo más importante.\n"
    "- Después, estas secciones, en este orden, separadas por una línea en blanco. Cada sección "
    "empieza con su emoji y su título en negrita y MAYÚSCULAS (por ejemplo, '⚠️ **ALERTAS**'), y "
    "cada punto va en su propia línea, empezando por '• ':\n"
    "⚠️ ALERTAS: alertas de seguridad o patrones escalados; si no hay, un solo punto '• Ninguna'.\n"
    "📥 DECIDIR EN LA APP: '• **patrón**: qué decidir en 1 · Detectar o 2 · Preparar', de mayor a "
    "menor prioridad; si no hay, '• Nada pendiente'.\n"
    "🔁 SEGUIMIENTOS: '• **14/10** · patrón: qué prueba llevar (3 · Seguir)', empezando por la "
    "fecha o la condición; si no toca ninguno esta semana, dilo en un punto y menciona el más "
    "próximo con su fecha en negrita.\n"
    "🛠️ TAREAS EN EL CLUB: '• **Rol:** qué hacer, con el dato clave en negrita (por ejemplo, el "
    "**sábado por la mañana** o a las **15:15**) (patrón)', un responsable por tarea (rol del "
    "perfil, nunca 'X o Y').\n"
    "⏳ ESPERANDO: '• qué se espera (**patrón**)'; si no hay, '• Nada'.\n"
    "Incluye TODAS las tareas en el club que salgan de los datos (las mismas que irían a la "
    "reunión del lunes): nunca quites una para ahorrar espacio; si hace falta, acorta la frase. "
    "Cada dato clave (hora, día, plazo) tiene que ser el de ESA tarea y ese patrón en los datos: "
    "nunca lo tomes de otro patrón ni te inventes uno; si no hay dato claro, no pongas ninguno. "
    "Como mucho DOS partes en negrita por línea, nunca frases enteras. Máximo unas 22 líneas. "
    "Frases cortas, sin repetir la misma tarea en dos secciones. Nombra los patrones de forma "
    "corta y reconocible (por ejemplo, 'arena en las pistas' en vez del nombre completo)."
)


WEEKLY_TITLES = ("Resumen de la semana", "ALERTAS", "DECIDIR EN LA APP", "SEGUIMIENTOS",
                 "TAREAS EN EL CLUB", "ESPERANDO")


def _tidy_weekly(text: str) -> str:
    """Makes sure the title and every section heading of the Monday message are
    in bold (**…**), even if Gemini forgets, so they stand out on the phone."""
    lines = []
    for line in (text or "").split("\n"):
        stripped = line.strip()
        for title in WEEKLY_TITLES:
            m = re.match(rf"^(\S*\s*)\**\s*({re.escape(title)})\s*\**\s*:?\s*$", stripped, re.I)
            if m:
                line = f"{m.group(1)}**{m.group(2)}**"
                break
        lines.append(line)
    return "\n".join(lines)


def run_weekly_summary() -> str:
    """The Monday message: what's waiting in the app, this week's tasks, what's on hold."""
    return _tidy_weekly(run_faq_agent(WEEKLY_QUESTION))


def run_faq_agent(question: str, history: list[dict] | None = None) -> str:
    if _blocked_without_login():
        return "Inicia sesión para usar Pala."
    try:
        counts = db.get_journey_counts()
    except Exception:
        counts = {}
    prompt = build_prompt(question, history or [], club_digest(), counts, load_club_profile(),
                          pending=pending_digest(), impact_figures=impact_digest())
    try:
        return _tidy_answer(generate(prompt, agent="pala"))
    except GeminiUnavailable as e:
        return str(e)


if __name__ == "__main__":
    print(run_faq_agent("¿Qué hago ahora?"))
