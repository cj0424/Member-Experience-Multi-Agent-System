"""
continuity_graph.py — the follow-up graph (Seguimiento page).

For every pattern whose kit is already approved:
  ⏸ Gate 3 — the owner reports, with tiered evidence, whether the action
  was actually carried out, plus any comments/reviews about the result
  → Outcome Check Agent decides: FLAG / CONTINUAR / CERRAR / PIVOTAR
  → every check-in is saved to pattern_history (with its full reasoning)

Then, for every PIVOTAR that isn't escalated:
  Action Planning (from pivot) → ⏸ owner approves / revises / discards
  the new plan. An approved new plan starts a new attempt: its old kit
  and verification method are cleared, so it appears again as "pendiente
  de kit" on Kits de Ejecución — the new plan always gets its own kit and
  is judged against its own checklist.

Fixes compared with the Phase 1 version:
- every read/write uses the pattern's id, never its name
- the decision is read only from the "Decisión:" line (a stray word like
  "PIVOTAR" inside the reasoning can't trigger a pivot anymore)
- after a Pivotar is approved, the old kit is cleared (db.start_new_attempt)
- discarding a pivot plan is saved: the pattern is escalated to the owner
- every event carries its attempt number, so Historial can show
  "attempt 2, cycle 1" instead of cycle numbers that restart
- no input(): human steps use interrupt(), like graph.py

Phase 3: every check-in automatically attaches what the four sources
(survey, incident log, staff notes, Google) said about this pattern's
topic since it was detected (db.source_evidence_summary). The owner sees
it before answering, and Outcome Check receives it together with the
owner's own comments. No mentions is not treated as proof it's fixed.
"""

import io
import re
from typing import TypedDict

import openpyxl
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langgraph.checkpoint.memory import MemorySaver

import db
from graph import narrate, feedback_with_history, existing_plans_context, new_thread, run_until_pause, resume
from outcome_check_agent import run_outcome_check_for
from action_planning_agent import run_action_planning_from_pivot, run_action_planning_revision

RAG_FOLDER = "data/rag_library"
MAX_PIVOTS = 2

EVIDENCE_TIERS = {
    1: "Evidencia ALTA — registro firmado",
    2: "Evidencia MEDIA — lo comprobó en persona quien registra el seguimiento",
    3: "Evidencia BAJA — me lo contaron, sin registro",
}


# ---------------------------------------------------------------------------
# Helpers (also used by the Seguimiento page)
# ---------------------------------------------------------------------------

def summarize_tracker(file_bytes: bytes) -> str:
    """Reads a filled-in .xlsx tracker (uploaded by the owner) and
    summarizes its real rows as evidence."""
    try:
        ws = openpyxl.load_workbook(io.BytesIO(file_bytes)).active
        rows = [
            " | ".join(str(c) for c in row if c is not None)
            for row in ws.iter_rows(min_row=5, values_only=True)
            if any(c not in (None, "") for c in row)
        ]
        if not rows:
            return "El archivo no tiene filas completadas todavía."
        return f"{len(rows)} entradas completadas en el registro:\n" + "\n".join(rows[-10:])
    except Exception as e:
        return f"No se pudo leer el archivo: {e}"


def extract_decision(outcome_text: str) -> str:
    """Reads ONLY the 'Decisión:' line (bold/heading markers allowed)."""
    for raw in outcome_text.split("\n"):
        line = re.sub(r"[*#_]", "", raw).strip()
        m = re.match(r"Decisi[oó]n\s*(?:final)?\s*:\s*(.*)", line, re.I)
        if m:
            value = m.group(1).upper()
            if "CERRAR" in value:
                return "CERRAR"
            if "PIVOTAR" in value:
                return "PIVOTAR"
            if "FLAG" in value:
                return "FLAG"
            if "CONTINUAR" in value:
                return "CONTINUAR"
    return "DESCONOCIDO"


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class ContinuityState(TypedDict, total=False):
    only_ids: list[int]     # optional: check only these patterns
    patterns: list[dict]    # patterns to check in this run
    index: int
    results: list[dict]     # one per check-in
    pivots: list[dict]      # new plans waiting for approval
    pivot_index: int
    pivot_results: list[dict]


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def load_node(state: ContinuityState) -> dict:
    narrate("🗂️ Leyendo los patrones en seguimiento...")
    patterns = db.get_patterns_in_followup()
    if state.get("only_ids"):
        patterns = [p for p in patterns if p["id"] in state["only_ids"]]
    narrate(f"✅ {len(patterns)} patrón(es) con kit aprobado, listos para revisar")
    return {"patterns": patterns, "index": 0, "results": [],
            "pivots": [], "pivot_index": 0, "pivot_results": []}


def checkin_node(state: ContinuityState) -> dict:
    """⏸ GATE 3 — one pattern per pass. The owner reports execution
    evidence and any feedback on the result; then Outcome Check decides."""
    patterns, i = state["patterns"], state["index"]
    if i >= len(patterns):
        return {}
    p = patterns[i]
    checkin_number = db.count_checkins(p["id"], p.get("attempt") or 1) + 1
    try:
        source_evidence = db.source_evidence_summary(p)
    except Exception as e:  # noqa: BLE001 - never block a check-in
        source_evidence = f"No se pudieron leer las fuentes: {e}"

    answer = interrupt({
        "type": "checkin",
        "index": i,
        "total": len(patterns),
        "pattern_id": p["id"],
        "pattern_name": p["pattern_name"],
        "approved_action": p.get("approved_action") or "",
        "verification_method": p.get("verification_method") or "",
        "attempt": p.get("attempt") or 1,
        "cycle": (p.get("cycles_since_approval") or 0) + 1,
        "checkin_number": checkin_number,
        "source_evidence": source_evidence,
    })

    results = list(state.get("results", []))
    if answer.get("action") == "skip":
        results.append({"pattern_id": p["id"], "pattern_name": p["pattern_name"], "decision": "OMITIDO"})
        return {"index": i + 1, "results": results}

    submitted_by = answer.get("submitted_by")          # role of the logged-in user (Phase 3)
    who_line = f"Seguimiento registrado por: {submitted_by}\n" if submitted_by else ""

    # 1. Execution evidence
    if answer.get("executed"):
        tier = int(answer.get("tier") or 3)
        verification_result = (f"{who_line}Confirmado — [{EVIDENCE_TIERS[tier]}] "
                               f"{answer.get('evidence_text', '').strip()}")
        cycles = (p.get("cycles_since_approval") or 0) + 1
    else:
        verification_result = f"{who_line}No confirmado todavía"
        cycles = p.get("cycles_since_approval") or 0

    db.update_pattern(p["id"], {"verification_result": verification_result,
                                "cycles_since_approval": cycles})
    p = {**p, "verification_result": verification_result, "cycles_since_approval": cycles}

    # 2. Outcome Check
    narrate(f"🔁 Evaluando resultados: {p['pattern_name']}...")
    feedback = (answer.get("feedback") or "").strip() or "Ninguna"
    combined = (f"EVIDENCIA AUTOMÁTICA DE LAS FUENTES (encuesta, incidencias, personal, Google):\n"
                f"{source_evidence}\n\nLO QUE INDICA EL PROPIETARIO SOBRE EL RESULTADO:\n{feedback}")
    outcome = run_outcome_check_for(
        p, new_reviews_since_approval=combined,
        rating_before=answer.get("rating_before") or "No disponible",
        rating_after=answer.get("rating_after") or "No disponible",
    )
    decision = extract_decision(outcome)
    attempt = p.get("attempt") or 1

    updates = {"last_decision": decision}
    pivots = list(state.get("pivots", []))
    escalated = False

    if decision == "CERRAR":
        updates["status"] = "closed"
    elif decision == "PIVOTAR":
        pivot_count = p.get("pivot_count") or 0
        if pivot_count >= MAX_PIVOTS:
            updates["status"] = "escalated"
            escalated = True
        else:
            updates["pivot_count"] = pivot_count + 1

    db.update_pattern(p["id"], updates)
    db.log_event(
        p["id"], p["pattern_name"], "check_in",
        narrative=outcome, decision=decision,
        evidence_summary=(f"{verification_result}\nComentarios sobre el resultado: {feedback}"
                          f"\nFuentes desde la detección:\n{source_evidence}"),
        attempt=attempt, cycle=cycles,
    )

    # 3. Pivot → new plan, with memory of what was tried and rejected
    if decision == "PIVOTAR" and not escalated:
        narrate(f"✍️ Preparando un enfoque distinto para: {p['pattern_name']}...")
        others = [k for k in db.get_all_patterns() if k["id"] != p["id"]]
        description = (p.get("pattern_description") or p["pattern_name"]) + existing_plans_context(others, [])
        text = run_action_planning_from_pivot(
            description, RAG_FOLDER, p.get("approved_action") or "", outcome,
            p.get("rejected_ideas") or "Ninguna",
        )
        pivots.append({"pattern_id": p["id"], "name": p["pattern_name"], "description": description,
                       "previous_action": p.get("approved_action") or "", "text": text})

    results.append({"pattern_id": p["id"], "pattern_name": p["pattern_name"],
                    "decision": "ESCALADO" if escalated else decision,
                    "narrative": outcome, "attempt": attempt, "cycle": cycles,
                    "checkin_number": checkin_number})
    return {"index": i + 1, "results": results, "pivots": pivots}


def pivot_review_node(state: ContinuityState) -> dict:
    """⏸ Approve / revise / discard a new plan after a Pivotar."""
    pivots, i = state["pivots"], state["pivot_index"]
    if i >= len(pivots):
        return {}
    item = pivots[i]

    decision = interrupt({
        "type": "pivot",
        "index": i,
        "total": len(pivots),
        "kind": "pivot",
        "pattern_id": item["pattern_id"],
        "pattern_name": item["name"],
        "text": item["text"],
    })
    action = decision.get("action")
    results = list(state.get("pivot_results", []))

    if action == "revise":
        feedback = decision.get("feedback", "").strip()
        revised = run_action_planning_revision(
            item["description"], RAG_FOLDER, item["text"],
            feedback_with_history(feedback, item.get("revisions", [])),
        )
        new_pivots = list(pivots)
        new_pivots[i] = {**item, "text": revised,
                         "revisions": item.get("revisions", []) + [{"text": item["text"], "feedback": feedback}]}
        return {"pivots": new_pivots}

    pid = item["pattern_id"]
    current_attempt = (db.get_pattern(pid) or {}).get("attempt") or 1
    for rev in item.get("revisions", []):
        db.append_rejected_idea(pid, db.rejected_entry(rev["text"], rev["feedback"]))
        db.log_event(pid, item["name"], "plan_revisado", narrative=rev["text"],
                     evidence_summary=f"Motivo del propietario: {rev['feedback']}", attempt=current_attempt)

    if action == "approve":
        new_attempt = db.start_new_attempt(pid, item["text"])
        db.log_event(pid, item["name"], "plan_aprobado", narrative=item["text"], attempt=new_attempt,
                     evidence_summary="Nuevo enfoque tras PIVOTAR")
        results.append({"pattern_name": item["name"], "outcome": "approved"})
    else:
        db.append_rejected_idea(pid, db.rejected_entry(item["text"], "el propietario descartó el nuevo enfoque"))
        db.update_pattern(pid, {"status": "escalated"})
        db.log_event(pid, item["name"], "descartado", narrative=item["text"], attempt=current_attempt,
                     evidence_summary="Nuevo enfoque descartado: el patrón pasa a revisión directa del propietario")
        results.append({"pattern_name": item["name"], "outcome": "discarded"})

    return {"pivot_index": i + 1, "pivot_results": results}


def after_checkin(state: ContinuityState) -> str:
    if state["index"] < len(state["patterns"]):
        return "checkin"
    return "pivot_review" if state.get("pivots") else END


def after_pivot(state: ContinuityState) -> str:
    return "pivot_review" if state["pivot_index"] < len(state["pivots"]) else END


_builder = StateGraph(ContinuityState)
_builder.add_node("load", load_node)
_builder.add_node("checkin", checkin_node)
_builder.add_node("pivot_review", pivot_review_node)
_builder.add_edge(START, "load")
_builder.add_conditional_edges("load", lambda s: "checkin" if s["patterns"] else END,
                               {"checkin": "checkin", END: END})
_builder.add_conditional_edges("checkin", after_checkin,
                               {"checkin": "checkin", "pivot_review": "pivot_review", END: END})
_builder.add_conditional_edges("pivot_review", after_pivot, {"pivot_review": "pivot_review", END: END})

continuity_graph = _builder.compile(checkpointer=MemorySaver())


# ---------------------------------------------------------------------------
# Terminal runner — for testing only; the owner uses Streamlit
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    config = new_thread()
    pending = run_until_pause(continuity_graph, {}, config)
    while pending:
        print(f"\n--- {pending['pattern_name']} ({pending['index'] + 1} de {pending['total']}) ---")
        if pending["type"] == "checkin":
            print(f"Cómo verificar: {pending['verification_method']}")
            done = input("¿Se ejecutó? (s/n, o 'o' para omitir): ").strip().lower()
            if done == "o":
                answer = {"action": "skip"}
            else:
                answer = {"executed": done == "s"}
                if done == "s":
                    answer["tier"] = int(input("Evidencia: 1=registro firmado, 2=lo comprobé yo, 3=me lo dijeron: ") or 3)
                    answer["evidence_text"] = input("¿Qué evidencia exactamente?: ")
                answer["feedback"] = input("Comentarios o reseñas sobre el resultado (Enter si ninguno): ")
                answer["rating_before"] = input("Valoración ANTES (Enter si no): ")
                answer["rating_after"] = input("Valoración AHORA (Enter si no): ")
        else:
            print(pending["text"])
            choice = input("¿Aprobar (a), pedir cambios (r), o descartar (d)?: ").strip().lower()
            answer = {"action": {"a": "approve", "r": "revise"}.get(choice, "discard")}
            if choice == "r":
                answer["feedback"] = input("¿Qué cambiarías?: ")
        pending = run_until_pause(continuity_graph, resume(answer), config)

    values = continuity_graph.get_state(config).values
    for r in values.get("results", []):
        print(f"🔁 {r['pattern_name']}: {r['decision']}")
    for r in values.get("pivot_results", []):
        print(f"{'✅' if r['outcome'] == 'approved' else '❌'} Nuevo enfoque — {r['pattern_name']}")
