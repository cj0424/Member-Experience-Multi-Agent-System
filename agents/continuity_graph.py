"""
Continuity Graph — Agent 4's real, connected workflow. Separate
from graph.py because this represents a genuinely different
real-world trigger: checking on patterns that were already
approved and executed a while ago, not discovering new ones.
Shares Supabase and reuses Action Planning / Execution Kit
functions when Pivotar requires a genuinely new attempt.
"""

from typing import TypedDict, Optional
from langgraph.graph import StateGraph, START, END

from outcome_check_agent import run_outcome_check_from_db, supabase
from action_planning_agent import run_action_planning_from_pivot
from execution_kit_agent import (
    run_execution_kit_agent,
    run_execution_kit_revision,
    extract_tracker_specs,
    build_tracker_excel,
    safe_filename,
)


class ContinuityState(TypedDict):
    """Shared state for this graph — a list of patterns due for
    checking, and the results/decisions made along the way."""
    due_patterns: Optional[list[dict]]
    outcome_results: Optional[list[dict]]
    new_recommendations: Optional[list[dict]]


def outcome_check_node(state: ContinuityState) -> dict:
    """Finds every pattern actually due for a check-in (status
    still 'open'), runs Agent 4 on each, and prints every result
    clearly — including FLAG cases, which must never be silently
    lost."""
    result = supabase.table("patterns").select("*").eq("status", "open").execute()
    due_patterns = result.data

    if not due_patterns:
        print("\nNo hay patrones pendientes de revisión en este momento.")
        return {"outcome_results": []}

    print(f"=== {len(due_patterns)} PATRONES PENDIENTES DE REVISIÓN ===\n")

    outcome_results = []
    for pattern in due_patterns:
        pattern_name = pattern["pattern_name"]
        print(f"\n--- Revisando: {pattern_name} ---\n")

        outcome_text = run_outcome_check_from_db(pattern_name)
        print(outcome_text)

        if "FLAG DE IMPLEMENTACIÓN" in outcome_text:
            print(f"\n🚩 ATENCIÓN: '{pattern_name}' requiere confirmación de ejecución antes de poder evaluarse.")

        outcome_results.append({
            "pattern_name": pattern_name,
            "pattern_data": pattern,
            "outcome_text": outcome_text
        })

    return {"outcome_results": outcome_results}


def route_after_outcome(state: ContinuityState) -> str:
    """Deterministic router — reads Agent 4's own explicit decision
    from its output text, no second LLM call needed since Agent 4
    already made the judgment. For every pattern that came back
    PIVOTAR, checks pivot_count first: if it's already failed twice,
    escalate for direct human review instead of looping again."""
    needs_new_plan = False

    for item in state["outcome_results"]:
        if "PIVOTAR" in item["outcome_text"]:
            current_count = item["pattern_data"].get("pivot_count", 0)

            if current_count >= 2:
                print(f"\n⚠️ ESCALADO: '{item['pattern_name']}' ha fallado 2 veces "
                      f"seguidas tras intentos reales. Esto requiere revisión "
                      f"directa del propietario, no otro intento automático.")
                supabase.table("patterns").update({"status": "escalated"}).eq(
                    "pattern_name", item["pattern_name"]
                ).execute()
            else:
                supabase.table("patterns").update({"pivot_count": current_count + 1}).eq(
                    "pattern_name", item["pattern_name"]
                ).execute()
                needs_new_plan = True

    return "action_planning_from_pivot" if needs_new_plan else END


def action_planning_from_pivot_node(state: ContinuityState) -> dict:
    """For every pattern that came back PIVOTAR (and hasn't hit the
    escalation limit), generates a genuinely new recommendation
    using the real outcome evidence — reusing run_action_planning_
    from_pivot(), the same tested function graph.py's design always
    intended for this exact case."""
    new_recommendations = []

    for item in state["outcome_results"]:
        if "PIVOTAR" not in item["outcome_text"]:
            continue

        current_count = item["pattern_data"].get("pivot_count", 0)
        if current_count > 2:
            continue  # already escalated in route_after_outcome, skip

        pattern_name = item["pattern_name"]
        previous_action = item["pattern_data"].get("approved_action", "")

        print(f"\n=== GENERANDO NUEVA RECOMENDACIÓN (PIVOTAR): {pattern_name} ===\n")
        new_rec = run_action_planning_from_pivot(
            pattern_name,
            "data/rag_library",
            previous_action,
            item["outcome_text"]
        )
        print(new_rec)

        new_recommendations.append({"pattern_name": pattern_name, "text": new_rec})

    return {"new_recommendations": new_recommendations}


def approval_node(state: ContinuityState) -> dict:
    """GATE 1, reused here for pivoted recommendations — same
    Approve/Revise/Discard pattern as graph.py's original gate,
    since a new attempt after Pivotar still needs real human
    sign-off before anything is prepared."""
    approved = []

    if not state["new_recommendations"]:
        return {"new_recommendations": []}

    for i, item in enumerate(state["new_recommendations"], start=1):
        pattern_name = item["pattern_name"]
        rec = item["text"]

        print(f"\n--- Nueva recomendación {i} de {len(state['new_recommendations'])}: {pattern_name} (pendiente de aprobación) ---\n")
        print(rec)
        decision = input("\n¿Aprobar (a), pedir cambios (r), o descartar (d)?: ").strip().lower()

        if decision == "a":
            supabase.table("patterns").update({
                "approved_action": rec,
                "status": "open",
                "cycles_since_approval": 0
            }).eq("pattern_name", pattern_name).execute()
            approved.append(item)
            print("✅ Aprobado y actualizado en Supabase.")
        else:
            print("Descartado — el patrón queda marcado para revisión manual.")

    return {"new_recommendations": approved}


def execution_kit_node(state: ContinuityState) -> dict:
    """GATE 2, reused here exactly as in graph.py — approving the
    materials for a newly-approved pivoted recommendation, with
    real file generation for any tracker piece."""
    if not state["new_recommendations"]:
        return {}

    for item in state["new_recommendations"]:
        pattern_name = item["pattern_name"]
        approved_action = item["text"]

        print(f"\n=== GENERANDO KIT DE EJECUCIÓN: {pattern_name} ===\n")
        kit = run_execution_kit_agent(approved_action)
        print(kit)

        decision = input(f"\n¿Aprobar (a), pedir cambios (r), o descartar (d) este kit para '{pattern_name}'?: ").strip().lower()

        final_kit = kit
        if decision == "r":
            feedback = input("¿Qué cambiarías?: ").strip()
            final_kit = run_execution_kit_revision(approved_action, kit, feedback)
            print("\n--- Kit revisado ---\n")
            print(final_kit)
            confirm = input("\n¿Aprobar este kit revisado? (a/d): ").strip().lower()
            if confirm != "a":
                print("Kit descartado.")
                continue
        elif decision != "a":
            print("Kit descartado.")
            continue

        trackers = extract_tracker_specs(final_kit)
        for spec in trackers:
            file_path = f"outputs/{safe_filename(spec['titulo'])}.xlsx"
            build_tracker_excel(spec, file_path)
            print(f"✅ Tracker Excel generado: {file_path}")

        print("✅ Kit aprobado.")

    return {}


graph_builder = StateGraph(ContinuityState)

graph_builder.add_node("outcome_check", outcome_check_node)
graph_builder.add_node("action_planning_from_pivot", action_planning_from_pivot_node)
graph_builder.add_node("approval", approval_node)
graph_builder.add_node("execution_kit", execution_kit_node)

graph_builder.add_edge(START, "outcome_check")
graph_builder.add_conditional_edges("outcome_check", route_after_outcome, {
    "action_planning_from_pivot": "action_planning_from_pivot",
    END: END
})
graph_builder.add_edge("action_planning_from_pivot", "approval")
graph_builder.add_edge("approval", "execution_kit")
graph_builder.add_edge("execution_kit", END)

continuity_graph = graph_builder.compile()


if __name__ == "__main__":
    continuity_graph.invoke({})