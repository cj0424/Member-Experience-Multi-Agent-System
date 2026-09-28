"""
graph.py — the two "forward" graphs of the system. Streamlit pages
run these; the terminal runner at the bottom is only for testing.

1. discovery_graph (Nuevos Patrones)
   Supabase memory → Insights → classify against what's already
   known → Action Planning → ⏸ Gate 1, one recommendation at a time.

2. kit_graph (Kits de Ejecución)
   patterns waiting for a kit → Execution Kit → ⏸ Gate 2, one kit at
   a time.

Human approval uses LangGraph's interrupt(): the graph pauses and
hands the UI what to show; the UI resumes it with the owner's
decision via Command(resume={...}). A checkpointer keeps the paused
graph alive between clicks, identified by a thread_id.

Memory: Gemini is stateless, so every node that needs history reads
it from Supabase (db.py) and passes it into the prompt. Every human
decision — approve, revise, discard — is written back, so the next
run knows about it.
"""

import json
import re
import uuid
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_stream_writer

import db
from insights_agent import run_insights_agent, client
from action_planning_agent import run_action_planning_agent, run_action_planning_revision
from execution_kit_agent import run_execution_kit_agent, run_execution_kit_revision

RAG_FOLDER = "data/rag_library"
REVIEW_FILE = "data/reviews/padel_club_reviews_anonymized.txt"
SURVEY_FILE = "data/reviews/padel_club_survey_sept_week3.txt"
MODEL = "gemini-3.7-flash"


def narrate(message: str):
    """Sends a progress line to whoever is streaming the graph
    (Streamlit's status box, or the terminal)."""
    try:
        get_stream_writer()({"step": message})
    except Exception:
        pass


def gemini_json(prompt: str):
    raw = client.models.generate_content(model=MODEL, contents=prompt).text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def normalize(name: str) -> str:
    return re.sub(r"[^a-záéíóúñü0-9 ]", "", (name or "").lower()).strip()


def feedback_with_history(feedback: str, revisions: list[dict]) -> str:
    """Each revision only saw the latest feedback, so an idea rejected in
    round 1 could come back in round 2. This adds every earlier rejection
    from the same review to the feedback Gemini receives."""
    if not revisions:
        return feedback
    earlier = "\n".join(f"- {db.rejected_entry(r['text'], r['feedback'])}" for r in revisions)
    return (
        f"{feedback}\n\nEN ESTA MISMA REVISIÓN YA SE DESCARTÓ (no lo vuelvas a proponer):\n{earlier}"
    )


# ===========================================================================
# 1. DISCOVERY GRAPH — Nuevos Patrones
# ===========================================================================

class DiscoveryState(TypedDict, total=False):
    known: list[dict]         # patterns already in Supabase at the start
    insights_text: str
    run_id: int               # this analysis, saved in insights_runs
    items: list[dict]         # recommendations waiting for Gate 1
    skipped: list[dict]       # patterns found but already handled
    not_detected: list[dict]  # known patterns NOT found active this run
    index: int
    results: list[dict]


def insights_node(state: DiscoveryState) -> dict:
    narrate("🗂️ Leyendo los patrones ya registrados en Supabase...")
    known = db.get_all_patterns()
    narrate("📖 Leyendo reseñas de Google y respuestas de encuesta...")
    text = run_insights_agent(REVIEW_FILE, SURVEY_FILE, known_patterns=db.format_known_patterns(known))
    return {"known": known, "insights_text": text}


def extract_patterns(insights_text: str) -> list[dict]:
    """Structured extraction of every ACTIVE confirmed pattern with its
    registry label. Falls back to splitting the text if JSON fails."""
    prompt = f"""A continuación hay un análisis de reseñas de un club de pádel.
Extrae ÚNICAMENTE los patrones CONFIRMADOS etiquetados como 🟢 ACTIVO.
No incluyas patrones 📁 HISTÓRICO, ni evidencia insuficiente.

ANÁLISIS:
{insights_text}

Responde ÚNICAMENTE con un array JSON. Cada elemento:
{{"nombre": "nombre del patrón",
  "texto": "el bloque completo del patrón, tal cual",
  "registro": "NUEVO" | "YA REGISTRADO" | "REAPARECE",
  "id": número del patrón registrado, o null si es NUEVO}}
Si no hay ningún patrón ACTIVO, responde []."""
    try:
        data = gemini_json(prompt)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, ValueError, IndexError):
        pass

    items = []
    for block in insights_text.split("🔍 PATRÓN")[1:]:
        text = "🔍 PATRÓN" + block.split("---")[0]
        if "HISTÓRICO" in text:
            continue
        name = text.split("\n")[0].replace("🔍 PATRÓN —", "").replace("🔍 PATRÓN", "").strip()
        match = re.search(r"Registro:\s*(YA REGISTRADO|REAPARECE)\s*—?\s*#(\d+)", text)
        items.append({
            "nombre": name,
            "texto": text,
            "registro": match.group(1) if match else "NUEVO",
            "id": int(match.group(2)) if match else None,
        })
    return items


def classify_node(state: DiscoveryState) -> dict:
    """Decides, in code, what happens to each pattern — Gemini's label
    is checked against Supabase, never trusted blindly. Saves the full
    analysis and every decision to insights_runs."""
    narrate("🧭 Comparando con lo que el sistema ya conoce...")
    known_by_id = {p["id"]: p for p in state["known"]}
    known_by_name = {normalize(p["pattern_name"]): p for p in state["known"]}

    found_list = extract_patterns(state["insights_text"])
    items, skipped, decisions, matched_ids = [], [], [], set()

    for found in found_list:
        name = (found.get("nombre") or "").strip()
        match = known_by_id.get(found.get("id")) or known_by_name.get(normalize(name))

        if not match:
            if found.get("registro") in ("YA REGISTRADO", "REAPARECE"):
                # Gemini says it's known but gave no valid id or name:
                # never risk a duplicate — show it to the owner as skipped.
                reason = "Posible duplicado de un patrón registrado — revísalo"
                skipped.append({"pattern_id": None, "name": name, "reason": reason})
                decisions.append({"patron": name, "decision": "omitido", "motivo": reason})
            else:
                items.append({"kind": "nuevo", "name": name, "description": found.get("texto", name)})
                decisions.append({"patron": name, "decision": "nuevo → Action Planning"})
            continue

        matched_ids.add(match["id"])
        status = match.get("status")
        if status == "closed":
            items.append({
                "kind": "reaparece",
                "pattern_id": match["id"],
                "name": match["pattern_name"],
                "description": found.get("texto", name),
                "previous_action": match.get("approved_action") or "",
                "rejected_ideas": match.get("rejected_ideas") or "",
            })
            decisions.append({"patron": match["pattern_name"], "id": match["id"],
                              "decision": "reaparece → Action Planning"})
        else:
            reason = {
                "open": "Ya está en seguimiento",
                "escalated": "Escalado — pendiente de tu revisión",
                "discarded": "Lo descartaste en un análisis anterior",
            }.get(status, "Ya registrado")
            skipped.append({"pattern_id": match["id"], "name": match["pattern_name"], "reason": reason})
            decisions.append({"patron": match["pattern_name"], "id": match["id"],
                              "decision": "omitido", "motivo": reason})

    not_detected = [
        {"pattern_id": p["id"], "name": p["pattern_name"], "status": p.get("status")}
        for p in state["known"]
        if p["id"] not in matched_ids and p.get("status") != "discarded"
    ]
    for p in not_detected:
        decisions.append({"patron": p["name"], "id": p["pattern_id"],
                          "decision": "no detectado como activo en este análisis"})

    run_id = db.save_insights_run(
        sources=f"{REVIEW_FILE} + {SURVEY_FILE}",
        analysis=state["insights_text"],
        found=found_list,
        decisions=decisions,
    )

    narrate(f"✅ {len(items)} patrón(es) para revisar · {len(skipped)} ya conocido(s)")
    return {"run_id": run_id, "items": items, "skipped": skipped,
            "not_detected": not_detected, "index": 0, "results": []}


def existing_plans_context(known: list[dict], proposed: list[dict]) -> str:
    """What already exists elsewhere, so a new plan doesn't duplicate it:
    plans approved for other patterns in Supabase, plus plans already
    proposed earlier in this same analysis."""
    lines = [
        f"- {p['pattern_name']}: {db.summarize_recommendation(p.get('approved_action') or '')}"
        for p in known if p.get("status") == "open" and p.get("approved_action")
    ] + [f"- {p['name']}: {db.summarize_recommendation(p['text'])}" for p in proposed]
    if not lines:
        return ""
    return (
        "\n\nCONTEXTO DEL SISTEMA — ACCIONES QUE YA EXISTEN PARA OTROS PATRONES "
        "(no propongas acciones que las dupliquen; si encaja, compleméntalas sin repetirlas):\n"
        + "\n".join(lines)
    )


def planning_node(state: DiscoveryState) -> dict:
    items = []
    for item in state["items"]:
        narrate(f"✍️ Generando recomendación para: {item['name']}...")
        context = existing_plans_context(state["known"], items)
        description = item["description"]
        if item["kind"] == "reaparece":
            description += (
                "\n\nCONTEXTO DEL SISTEMA: este patrón ya se cerró antes como resuelto, "
                "pero vuelve a aparecer.\n"
                f"ACCIÓN QUE SE APLICÓ ANTES:\n{item['previous_action']}\n"
                f"IDEAS YA DESCARTADAS POR EL PROPIETARIO (no las repitas):\n"
                f"{item['rejected_ideas'] or 'Ninguna'}"
            )
        items.append({**item, "context": context,
                      "text": run_action_planning_agent(description + context, RAG_FOLDER)})
    return {"items": items}


def _log_plan_story(pattern_id, item, attempt, run_id):
    """Writes this pattern's discovery story to pattern_history: how it
    was found, then every version the owner asked to change."""
    first_event = "reaparece" if item["kind"] == "reaparece" else "detectado"
    db.log_event(pattern_id, item["name"], first_event, narrative=item["description"],
                 attempt=attempt, insights_run_id=run_id)
    for rev in item.get("revisions", []):
        db.log_event(pattern_id, item["name"], "plan_revisado", narrative=rev["text"],
                     evidence_summary=f"Motivo del propietario: {rev['feedback']}", attempt=attempt)


def review_recommendation_node(state: DiscoveryState) -> dict:
    """⏸ GATE 1. Handles ONE recommendation per pass: pauses for the
    owner's decision, applies it, then loops. Everything before
    interrupt() only reads state, because LangGraph re-runs the node
    from the top when it resumes."""
    items, i = state["items"], state["index"]
    if i >= len(items):
        return {}
    item = items[i]

    decision = interrupt({
        "type": "recommendation",
        "index": i,
        "total": len(items),
        "kind": item["kind"],
        "pattern_name": item["name"],
        "text": item["text"],
    })
    action = decision.get("action")
    results = list(state.get("results", []))
    run_id = state.get("run_id")

    if action == "revise":
        feedback = decision.get("feedback", "").strip()
        revised = run_action_planning_revision(
            item["description"] + item.get("context", ""), RAG_FOLDER, item["text"],
            feedback_with_history(feedback, item.get("revisions", [])),
        )
        revisions = item.get("revisions", []) + [{"text": item["text"], "feedback": feedback}]
        new_items = list(items)
        new_items[i] = {**item, "text": revised, "revisions": revisions}
        return {"items": new_items}

    rejected = [db.rejected_entry(r["text"], r["feedback"]) for r in item.get("revisions", [])]

    if action == "approve":
        if item["kind"] == "reaparece":
            pattern_id = item["pattern_id"]
            attempt = db.start_new_attempt(pattern_id, item["text"], item["description"], reset_pivots=True)
            for entry in rejected:
                entry = db.drop_kept_ideas(entry, item["text"])   # never record kept options as rejected
                if entry:
                    db.append_rejected_idea(pattern_id, entry)
        else:
            row = db.create_pattern(item["name"], item["description"], item["text"],
                                    rejected_ideas="\n".join(f"- {e}" for e in rejected) or None)
            pattern_id, attempt = row.get("id"), 1
        _log_plan_story(pattern_id, item, attempt, run_id)
        db.log_event(pattern_id, item["name"], "plan_aprobado", narrative=item["text"], attempt=attempt)
        results.append({"pattern_name": item["name"], "outcome": "approved"})
    else:
        if item["kind"] == "reaparece":
            pattern_id = item["pattern_id"]
            attempt = (db.get_pattern(pattern_id) or {}).get("attempt") or 1
            for entry in rejected + [db.rejected_entry(item["text"], "el propietario descartó la recomendación")]:
                db.append_rejected_idea(pattern_id, entry)
        else:
            row = db.record_discarded_pattern(item["name"], item["description"], item["text"],
                                              rejected_ideas="\n".join(f"- {e}" for e in rejected) or None)
            pattern_id, attempt = row.get("id"), 1
        _log_plan_story(pattern_id, item, attempt, run_id)
        db.log_event(pattern_id, item["name"], "descartado", narrative=item["text"], attempt=attempt)
        results.append({"pattern_name": item["name"], "outcome": "discarded"})

    return {"index": i + 1, "results": results}


def after_review(state: DiscoveryState) -> str:
    return "review" if state["index"] < len(state["items"]) else END


_discovery = StateGraph(DiscoveryState)
_discovery.add_node("insights", insights_node)
_discovery.add_node("classify", classify_node)
_discovery.add_node("planning", planning_node)
_discovery.add_node("review", review_recommendation_node)
_discovery.add_edge(START, "insights")
_discovery.add_edge("insights", "classify")
_discovery.add_edge("classify", "planning")
_discovery.add_edge("planning", "review")
_discovery.add_conditional_edges("review", after_review, {"review": "review", END: END})

discovery_graph = _discovery.compile(checkpointer=MemorySaver())


# ===========================================================================
# 2. KIT GRAPH — Kits de Ejecución
# ===========================================================================

class KitState(TypedDict, total=False):
    only_ids: list[int]     # optional: draft kits only for these patterns
    kits: list[dict]
    index: int
    results: list[dict]


def extract_verification_method(kit_text: str) -> str:
    """Reads the 'Cómo verificar' line directly; asks Gemini only if
    the format varies."""
    match = re.search(r"C[oó]mo verificar\s*:?\**\s*:?\s*(.+)", kit_text)
    if match and match.group(1).replace("**", "").strip():
        return match.group(1).replace("**", "").strip()

    prompt = f"""Del siguiente kit de ejecución, extrae ÚNICAMENTE el texto del
método de verificación (la línea "Cómo verificar"), sin la etiqueta.
Si no existe, responde exactamente: NO_ENCONTRADO

KIT:
{kit_text}"""
    result = client.models.generate_content(model=MODEL, contents=prompt).text.strip()
    return "Ver kit de ejecución completo" if result in ("", "NO_ENCONTRADO") else result


def draft_kits_node(state: KitState) -> dict:
    pending = db.get_patterns_pending_kit()
    if state.get("only_ids"):
        pending = [p for p in pending if p["id"] in state["only_ids"]]
    narrate(f"📥 Leyendo {len(pending)} recomendación(es) aprobada(s) sin kit...")
    kits = []
    for p in pending:
        narrate(f"✍️ Redactando kit para: {p['pattern_name']}...")
        kits.append({
            "pattern_id": p["id"],
            "pattern_name": p["pattern_name"],
            "attempt": p.get("attempt") or 1,
            "approved_action": p.get("approved_action") or "",
            "text": run_execution_kit_agent(p.get("approved_action") or ""),
        })
    return {"kits": kits, "index": 0, "results": []}


def review_kit_node(state: KitState) -> dict:
    """⏸ GATE 2, one kit per pass. Discarding saves nothing: the
    pattern stays 'pending kit' and can be drafted again later."""
    kits, i = state["kits"], state["index"]
    if i >= len(kits):
        return {}
    kit = kits[i]

    decision = interrupt({
        "type": "kit",
        "index": i,
        "total": len(kits),
        "pattern_name": kit["pattern_name"],
        "text": kit["text"],
    })
    action = decision.get("action")
    results = list(state.get("results", []))

    if action == "revise":
        feedback = decision.get("feedback", "")
        revised = run_execution_kit_revision(
            kit["approved_action"], kit["text"], feedback_with_history(feedback, kit.get("revisions", []))
        )
        revisions = kit.get("revisions", []) + [{"text": kit["text"], "feedback": feedback}]
        new_kits = list(kits)
        new_kits[i] = {**kit, "text": revised, "revisions": revisions}
        return {"kits": new_kits}

    for rev in kit.get("revisions", []):
        db.log_event(kit["pattern_id"], kit["pattern_name"], "kit_revisado", narrative=rev["text"],
                     evidence_summary=f"Motivo del propietario: {rev['feedback']}", attempt=kit["attempt"])

    if action == "approve":
        method = extract_verification_method(kit["text"])
        db.save_kit(kit["pattern_id"], kit["text"], method)
        db.log_event(kit["pattern_id"], kit["pattern_name"], "kit_aprobado", narrative=kit["text"],
                     evidence_summary=f"Cómo verificar: {method}", attempt=kit["attempt"])
        results.append({"pattern_name": kit["pattern_name"], "outcome": "approved"})
    else:
        db.log_event(kit["pattern_id"], kit["pattern_name"], "kit_descartado", narrative=kit["text"],
                     attempt=kit["attempt"])
        results.append({"pattern_name": kit["pattern_name"], "outcome": "discarded"})

    return {"index": i + 1, "results": results}


def after_kit_review(state: KitState) -> str:
    return "review" if state["index"] < len(state["kits"]) else END


_kits = StateGraph(KitState)
_kits.add_node("draft", draft_kits_node)
_kits.add_node("review", review_kit_node)
_kits.add_edge(START, "draft")
_kits.add_edge("draft", "review")
_kits.add_conditional_edges("review", after_kit_review, {"review": "review", END: END})

kit_graph = _kits.compile(checkpointer=MemorySaver())


# ===========================================================================
# Helpers the Streamlit pages (and the terminal runner) use
# ===========================================================================

def new_thread() -> dict:
    return {"configurable": {"thread_id": str(uuid.uuid4())}}


def run_until_pause(graph, graph_input, config, on_step=print):
    """Runs (or resumes) a graph until it pauses or finishes, sending
    every narration line to on_step. Returns the pending interrupt
    payload, or None if the graph finished."""
    for chunk in graph.stream(graph_input, config, stream_mode="custom"):
        if isinstance(chunk, dict) and "step" in chunk:
            on_step(chunk["step"])
    snapshot = graph.get_state(config)
    for task in snapshot.tasks:
        if task.interrupts:
            return task.interrupts[0].value
    return None


def resume(decision: dict) -> Command:
    return Command(resume=decision)


# ===========================================================================
# Terminal runner — for testing only; the owner uses Streamlit
# ===========================================================================

def _cli(graph, label: str):
    config = new_thread()
    pending = run_until_pause(graph, {}, config)
    analysis = graph.get_state(config).values.get("insights_text")
    if analysis:
        print("\n=== ANÁLISIS COMPLETO DE INSIGHTS ===\n")
        print(analysis)
        print("\n=====================================\n")
    while pending:
        print(f"\n--- {label} {pending['index'] + 1} de {pending['total']}: {pending['pattern_name']} ---\n")
        print(pending["text"])
        choice = input("\n¿Aprobar (a), pedir cambios (r), o descartar (d)?: ").strip().lower()
        decision = {"action": {"a": "approve", "r": "revise"}.get(choice, "discard")}
        if choice == "r":
            decision["feedback"] = input("¿Qué cambiarías?: ").strip()
        pending = run_until_pause(graph, resume(decision), config)

    values = graph.get_state(config).values
    for s in values.get("skipped", []):
        print(f"⏭️  {s['name']} — {s['reason']}")
    for n in values.get("not_detected", []):
        print(f"💤 {n['name']} — No detectado como activo en este análisis")
    for r in values.get("results", []):
        print(f"{'✅' if r['outcome'] == 'approved' else '❌'} {r['pattern_name']}")


if __name__ == "__main__":
    which = input("¿Qué grafo? (1 = descubrimiento, 2 = kits): ").strip()
    if which == "2":
        _cli(kit_graph, "Kit")
    else:
        _cli(discovery_graph, "Recomendación")