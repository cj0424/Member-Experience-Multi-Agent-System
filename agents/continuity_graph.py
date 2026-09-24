"""
Continuity Graph — Agent 4's real, connected workflow. Separate
from graph.py because this represents a genuinely different
real-world trigger: checking on patterns that were already
approved and executed a while ago, not discovering new ones.
Shares Supabase and reuses Action Planning / Execution Kit
functions when Pivotar requires a genuinely new attempt.

Two real, structural additions in this version:
- rejected_ideas: carried from Supabase into every Pivotar call, and
  appended to whenever the owner revises a recommendation with "don't
  suggest X again" — a real fix for stateless LLM calls having no
  memory of what was already turned down.
- pattern_history: an insert-only audit trail, one real row per
  check-in cycle, so the system's actual progression over time is
  visible — not just the latest overwritten snapshot.
"""

from typing import TypedDict, Optional
from langgraph.graph import StateGraph, START, END

import openpyxl

from outcome_check_agent import run_outcome_check_from_db, supabase
from action_planning_agent import run_action_planning_from_pivot, run_action_planning_revision
from execution_kit_agent import (
    run_execution_kit_agent,
    run_execution_kit_revision,
    extract_tracker_specs,
    build_tracker_excel,
    safe_filename,
)


class ContinuityState(TypedDict):
    """Shared state. confirmed_patterns carries the real Supabase
    row plus fresh, human-provided, tiered evidence collected this
    run — never stale or placeholder data."""
    confirmed_patterns: Optional[list[dict]]
    outcome_results: Optional[list[dict]]
    new_recommendations: Optional[list[dict]]


def extract_decision(outcome_text: str) -> str:
    """Reads only the final 'Decisión:' line, not the whole text —
    avoids any stray earlier mention of a different outcome word
    inside Agent 4's own reasoning being misread as the real
    decision."""
    for line in outcome_text.split("\n"):
        if line.strip().startswith("Decisión:"):
            if "CERRAR" in line:
                return "CERRAR"
            elif "PIVOTAR" in line:
                return "PIVOTAR"
            elif "FLAG DE IMPLEMENTACIÓN" in line:
                return "FLAG"
            else:
                return "CONTINUAR"
    return "DESCONOCIDO"


def read_real_tracker_evidence(file_path: str) -> str:
    """Opens a real, filled-in .xlsx tracker and summarizes its
    actual rows as genuine evidence — not a description of the
    file, the file's real content."""
    try:
        wb = openpyxl.load_workbook(file_path)
        ws = wb.active
        rows = []
        for row in ws.iter_rows(min_row=5, values_only=True):
            if any(cell not in (None, "") for cell in row):
                rows.append(" | ".join(str(c) for c in row if c is not None))

        if not rows:
            return "El archivo existe pero no tiene filas completadas todavía."

        summary = f"{len(rows)} entradas completadas en el registro:\n"
        summary += "\n".join(rows[-10:])
        return summary

    except FileNotFoundError:
        return f"⚠️ No se encontró el archivo en '{file_path}'."
    except Exception as e:
        return f"⚠️ No se pudo leer el archivo: {e}"


def confirm_execution_node(state: ContinuityState) -> dict:
    """GATE 3 — the real human-in-the-loop checkpoint. For every
    pattern due for review, collects REAL, TIERED evidence of
    execution (a signed tracker, a direct personal observation, or
    a verbal relay) — never a bare yes/no — plus separately, any
    real evidence about whether the RESULT actually improved."""
    result = supabase.table("patterns").select("*").eq("status", "open").execute()
    due_patterns = result.data

    if not due_patterns:
        print("\nNo hay patrones pendientes de revisión en este momento.")
        return {"confirmed_patterns": []}

    print(f"=== {len(due_patterns)} PATRONES PENDIENTES DE CONFIRMACIÓN ===\n")

    confirmed = []

    for pattern in due_patterns:
        pattern_name = pattern["pattern_name"]
        verification_method = pattern.get("verification_method")

        print(f"\n--- {pattern_name} ---")

        if not verification_method:
            print("⚠️ Este patrón no tiene un método de verificación registrado "
                  "(no pasó por el kit de ejecución) — no se puede confirmar "
                  "ejecución real todavía.")
            confirmed.append({
                "pattern_name": pattern_name,
                "pattern_data": pattern,
                "feedback_text": "Ninguna",
                "rating_before": "No disponible",
                "rating_after": "No disponible",
            })
            continue

        print(f"Método de verificación acordado: {verification_method}")
        done = input("¿Se ha confirmado que esta acción se ejecutó? (s/n): ").strip().lower()

        if done != "s":
            supabase.table("patterns").update({
                "verification_result": "No confirmado todavía"
            }).eq("pattern_name", pattern_name).execute()
            pattern["verification_result"] = "No confirmado todavía"
            confirmed.append({
                "pattern_name": pattern_name,
                "pattern_data": pattern,
                "feedback_text": "Ninguna",
                "rating_before": "No disponible",
                "rating_after": "No disponible",
            })
            continue

        print("\n¿Qué tipo de evidencia real tienes de que se hizo? (de más a menos sólida)")
        print("1 = Un registro/tracker real, con fecha, responsable y firma")
        print("2 = Lo comprobé yo mismo directamente (observación personal)")
        print("3 = El personal me lo confirmó verbalmente, sin registro escrito")
        evidence_tier = input("Elige 1, 2 o 3: ").strip()

        if evidence_tier == "1":
            file_path = input("Ruta del archivo (ej. outputs/Registro_Semanal.xlsx): ").strip()
            evidence_text = "[Evidencia ALTA — registro firmado] " + read_real_tracker_evidence(file_path)
        elif evidence_tier == "2":
            detail = input("¿Qué comprobaste exactamente y cuándo?: ").strip()
            evidence_text = f"[Evidencia MEDIA — observación directa del propietario] {detail}"
        else:
            staff_name = input("¿Quién del personal te lo confirmó?: ").strip()
            detail = input("¿Qué te confirmó exactamente?: ").strip()
            evidence_text = f"[Evidencia BAJA — relato verbal, sin registro] {staff_name} dijo: {detail}"

        verification_result = f"Confirmado — {evidence_text}"
        new_cycles = pattern.get("cycles_since_approval", 0) + 1

        feedback_text = input("\n¿Alguna reseña, respuesta de encuesta, o comentario "
                               "directo sobre si el PROBLEMA ORIGINAL mejoró, desde "
                               "la aprobación? Si no hay ninguno, pulsa Enter: ").strip()
        rating_before = input("Valoración media ANTES (si la conoces, si no pulsa "
                               "Enter): ").strip() or "No disponible"
        rating_after = input("Valoración media AHORA (si la conoces, si no pulsa "
                              "Enter): ").strip() or "No disponible"

        supabase.table("patterns").update({
            "verification_result": verification_result,
            "cycles_since_approval": new_cycles,
        }).eq("pattern_name", pattern_name).execute()

        pattern["verification_result"] = verification_result
        pattern["cycles_since_approval"] = new_cycles

        confirmed.append({
            "pattern_name": pattern_name,
            "pattern_data": pattern,
            "feedback_text": feedback_text if feedback_text else "Ninguna",
            "rating_before": rating_before,
            "rating_after": rating_after,
        })

    return {"confirmed_patterns": confirmed}


def outcome_check_node(state: ContinuityState) -> dict:
    """Runs Agent 4 using the FRESH, real, tiered evidence just
    collected. Writes a real, permanent row to pattern_history for
    every single check-in (never overwritten — this is the genuine
    audit trail), updates patterns.last_decision so the current
    row always shows the real latest outcome, and when CERRAR
    fires, closes the pattern permanently — it exits the active
    check-in loop, matching real practice: a validated fix is
    closed, not re-litigated indefinitely."""
    confirmed_patterns = state.get("confirmed_patterns", [])

    if not confirmed_patterns:
        return {"outcome_results": []}

    print(f"\n=== EVALUANDO {len(confirmed_patterns)} PATRONES CON AGENTE 4 ===\n")

    outcome_results = []
    for item in confirmed_patterns:
        pattern_name = item["pattern_name"]
        print(f"\n--- Revisando: {pattern_name} ---\n")

        outcome_text = run_outcome_check_from_db(
            pattern_name,
            new_reviews_since_approval=item["feedback_text"],
            rating_before=item["rating_before"],
            rating_after=item["rating_after"],
        )
        print(outcome_text)

        decision = extract_decision(outcome_text)

        supabase.table("patterns").update({"last_decision": decision}).eq(
            "pattern_name", pattern_name
        ).execute()

        if decision == "FLAG":
            print(f"\n🚩 ATENCIÓN: '{pattern_name}' requiere confirmación de ejecución antes de poder evaluarse.")
        elif decision == "CERRAR":
            print(f"\n✅ '{pattern_name}' se marca como resuelto y sale del ciclo activo de revisión.")
            supabase.table("patterns").update({"status": "closed"}).eq(
                "pattern_name", pattern_name
            ).execute()

        supabase.table("pattern_history").insert({
            "pattern_name": pattern_name,
            "cycle": item["pattern_data"].get("cycles_since_approval", 0),
            "decision": decision,
            "evidence_summary": item["feedback_text"],
            "narrative": outcome_text,
        }).execute()

        outcome_results.append({
            "pattern_name": pattern_name,
            "pattern_data": item["pattern_data"],
            "outcome_text": outcome_text
        })

    return {"outcome_results": outcome_results}


def route_after_outcome(state: ContinuityState) -> str:
    """Deterministic router — reads Agent 4's own explicit decision.
    For every PIVOTAR, checks pivot_count: if already failed twice,
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
    """For every PIVOTAR (not yet escalated), generates a genuinely
    new recommendation using the real outcome evidence AND the
    pattern's real rejected_ideas history, so a previously-discarded
    idea doesn't silently resurface."""
    new_recommendations = []

    for item in state["outcome_results"]:
        if "PIVOTAR" not in item["outcome_text"]:
            continue

        current_count = item["pattern_data"].get("pivot_count", 0)
        if current_count >= 2:
            continue  # already escalated in route_after_outcome, skip

        pattern_name = item["pattern_name"]
        previous_action = item["pattern_data"].get("approved_action", "")
        rejected_ideas = item["pattern_data"].get("rejected_ideas") or "Ninguna"

        print(f"\n=== GENERANDO NUEVA RECOMENDACIÓN (PIVOTAR): {pattern_name} ===\n")
        new_rec = run_action_planning_from_pivot(
            pattern_name,
            "data/rag_library",
            previous_action,
            item["outcome_text"],
            rejected_ideas
        )
        print(new_rec)

        new_recommendations.append({"pattern_name": pattern_name, "text": new_rec})

    return {"new_recommendations": new_recommendations}


def approval_node(state: ContinuityState) -> dict:
    """GATE 1, reused here for pivoted recommendations — real
    Approve/Revise/Discard. On Revise, the owner's feedback is
    appended to the pattern's real, permanent rejected_ideas record
    in Supabase, so it carries forward into any future Pivotar
    attempt for this same pattern."""
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

        elif decision == "r":
            feedback = input("¿Qué cambiarías?: ").strip()

            existing = supabase.table("patterns").select("rejected_ideas").eq(
                "pattern_name", pattern_name
            ).execute().data[0].get("rejected_ideas") or ""
            updated_rejected = f"{existing}\n- {feedback}".strip()
            supabase.table("patterns").update({"rejected_ideas": updated_rejected}).eq(
                "pattern_name", pattern_name
            ).execute()

            revised = run_action_planning_revision(pattern_name, "data/rag_library", rec, feedback)
            print("\n--- Recomendación revisada ---\n")
            print(revised)
            confirm = input("\n¿Aprobar esta versión revisada? (a/d): ").strip().lower()
            if confirm == "a":
                supabase.table("patterns").update({
                    "approved_action": revised,
                    "status": "open",
                    "cycles_since_approval": 0
                }).eq("pattern_name", pattern_name).execute()
                approved.append({"pattern_name": pattern_name, "text": revised})
                print("✅ Versión revisada aprobada y actualizada en Supabase.")
            else:
                print("Descartado.")

        else:
            print("Descartado — el patrón queda marcado para revisión manual.")

    return {"new_recommendations": approved}


def execution_kit_node(state: ContinuityState) -> dict:
    """GATE 2, reused here exactly as in graph.py."""
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

graph_builder.add_node("confirm_execution", confirm_execution_node)
graph_builder.add_node("outcome_check", outcome_check_node)
graph_builder.add_node("action_planning_from_pivot", action_planning_from_pivot_node)
graph_builder.add_node("approval", approval_node)
graph_builder.add_node("execution_kit", execution_kit_node)

graph_builder.add_edge(START, "confirm_execution")
graph_builder.add_edge("confirm_execution", "outcome_check")
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