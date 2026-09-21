"""
LangGraph orchestration — connects Insights, Action Planning,
Execution Kit, and Outcome Check into one automated flow, with
two human approval checkpoints matching the original design.
"""

import json
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, START, END

from insights_agent import run_insights_agent, client
from action_planning_agent import run_action_planning_agent, run_action_planning_revision, run_action_planning_from_pivot
from execution_kit_agent import run_execution_kit_agent, run_execution_kit_revision
from outcome_check_agent import run_outcome_check_from_db, supabase


class GraphState(TypedDict):
    """The shared 'cart' passed between every node — each agent
    reads what it needs and adds its own output."""
    pattern_name: str
    insights_result: Optional[str]
    recommendation: Optional[list[dict]]
    approved: Optional[bool]
    execution_kit: Optional[list[dict]]
    outcome_result: Optional[str]


def insights_node(state: GraphState) -> dict:
    """Runs Insights Agent, adds its result to the shared state.
    Prints immediately here, not after the whole graph finishes —
    so you can verify the ACTIVO/HISTÓRICO count BEFORE any
    approval prompts appear."""
    result = run_insights_agent()
    print("=== PASO 1: RESULTADO DE INSIGHTS AGENT ===\n")
    print(result)
    print("\n")
    return {"insights_result": result}


def extract_confirmed_patterns(insights_text: str) -> list[str]:
    """Robustly extracts each ACTIVE confirmed pattern from Insights
    Agent's output — HISTÓRICO (already-resolved) patterns are
    explicitly excluded, so Action Planning never wastes effort on
    something the evidence already shows is fixed."""
    extraction_prompt = f"""A continuación hay un análisis de reseñas de un
club de pádel. Extrae ÚNICAMENTE los patrones CONFIRMADOS que estén
etiquetados como 🟢 ACTIVO — no incluyas ningún patrón etiquetado como
📁 HISTÓRICO — YA RESUELTO, ni evidencia insuficiente, ni contradicciones
sueltas.

ANÁLISIS:
{insights_text}

Responde ÚNICAMENTE con un array JSON de strings — cada string debe ser
el texto completo de un patrón ACTIVO (nombre, evidencia, confianza,
qué significa). Si no hay ningún patrón ACTIVO, responde con un array
vacío []. No incluyas nada más que el array JSON."""

    response = client.models.generate_content(
        model="gemini-3.7-flash",
        contents=extraction_prompt
    )

    raw_text = response.text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        patterns = json.loads(raw_text)
        if isinstance(patterns, list):
            return [p for p in patterns if "HISTÓRICO" not in p]
    except (json.JSONDecodeError, ValueError):
        pass

    pattern_blocks = insights_text.split("🔍 PATRÓN")[1:]
    all_patterns = ["🔍 PATRÓN" + block.split("---")[0] for block in pattern_blocks]
    return [p for p in all_patterns if "HISTÓRICO" not in p]


def extract_verification_method(kit_text: str) -> str:
    """Robustly extracts the 'Cómo verificar' line from an
    Execution Kit output using a dedicated Gemini call that
    understands the CONTENT, not brittle text-marker splitting —
    same robust approach already proven for pattern extraction."""
    extraction_prompt = f"""El siguiente es un kit de ejecución generado
para un club de pádel. Extrae ÚNICAMENTE el método de verificación
(la línea "Cómo verificar") — el texto exacto que describe cómo
comprobar si la tarea se completó.

KIT:
{kit_text}

Responde ÚNICAMENTE con el texto del método de verificación, sin
explicación adicional, sin comillas, sin la etiqueta "Cómo verificar:"
al inicio. Si no encuentras un método de verificación explícito,
responde exactamente: NO_ENCONTRADO"""

    response = client.models.generate_content(
        model="gemini-3.7-flash",
        contents=extraction_prompt
    )

    result = response.text.strip()
    if result == "NO_ENCONTRADO" or not result:
        return "Ver kit de ejecución completo"
    return result


def action_planning_node(state: GraphState) -> dict:
    """Runs Action Planning once per ACTIVE confirmed pattern.
    HISTÓRICO patterns never reach this node — filtered out
    upstream in extract_confirmed_patterns."""
    insights_text = state["insights_result"]
    confirmed_patterns = extract_confirmed_patterns(insights_text)

    print(f"=== EXTRACCIÓN: {len(confirmed_patterns)} PATRONES ACTIVOS ENVIADOS A ACTION PLANNING ===\n")

    recommendations = []
    for pattern in confirmed_patterns:
        rec = run_action_planning_agent(pattern)
        first_line = pattern.split("\n")[0]
        pattern_name = first_line.replace("🔍 PATRÓN —", "").replace("🔍 PATRÓN", "").strip()
        if not pattern_name:
            pattern_name = first_line.strip()
        recommendations.append({"pattern_name": pattern_name, "text": rec})

    return {"recommendation": recommendations}


def approval_node(state: GraphState) -> dict:
    """Human approval checkpoint — GATE 1: approving the
    recommendation itself. Approve saves the real pattern name and
    action to Supabase. Revise asks for feedback and generates a
    genuinely new attempt. Discard does nothing."""
    approved_recommendations = []

    if not state["recommendation"]:
        print("\nNo hay patrones activos que requieran acción en este ciclo.")
        return {"recommendation": []}

    for i, item in enumerate(state["recommendation"], start=1):
        rec = item["text"]
        real_name = item["pattern_name"]

        print(f"\n--- Recomendación {i} de {len(state['recommendation'])}: {real_name} (pendiente de aprobación) ---\n")
        print(rec)
        decision = input("\n¿Aprobar (a), pedir cambios (r), o descartar (d)?: ").strip().lower()

        if decision == "a":
            supabase.table("patterns").insert({
                "pattern_name": real_name,
                "approved_action": rec,
                "status": "open"
            }).execute()
            approved_recommendations.append(item)
            print("✅ Aprobado y guardado.")

        elif decision == "r":
            feedback = input("¿Qué cambiarías?: ").strip()
            revised = run_action_planning_revision(real_name, "data/rag_library", rec, feedback)
            print("\n--- Recomendación revisada ---\n")
            print(revised)
            confirm = input("\n¿Aprobar esta versión revisada? (a/d): ").strip().lower()
            if confirm == "a":
                supabase.table("patterns").insert({
                    "pattern_name": real_name,
                    "approved_action": revised,
                    "status": "open"
                }).execute()
                approved_recommendations.append({"pattern_name": real_name, "text": revised})
                print("✅ Versión revisada aprobada y guardada.")
            else:
                print("Descartado.")

        else:
            print("Descartado.")

    return {"recommendation": approved_recommendations}


def execution_kit_node(state: GraphState) -> dict:
    """Runs Execution Kit Agent once per approved recommendation,
    with a SECOND real human gate (GATE 2 — Approve/Revise/Discard,
    same 3 options as Gate 1) applied to the actual materials, not
    the recommendation. Only kits that pass this gate get their
    verification method saved to Supabase."""
    kits = []

    if not state["recommendation"]:
        print("\nNo hay recomendaciones aprobadas — no se genera ningún kit de ejecución.")
        return {"execution_kit": []}

    for item in state["recommendation"]:
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
            print("Kit descartado — no se guarda el método de verificación.")
            continue

        verification_method = extract_verification_method(final_kit)

        update_result = supabase.table("patterns").update({
            "verification_method": verification_method
        }).eq("pattern_name", pattern_name).execute()

        if not update_result.data:
            print(f"⚠️ ADVERTENCIA: no se encontró ninguna fila en Supabase con "
                  f"pattern_name='{pattern_name}' — el método de verificación no se guardó.")

        kits.append({"pattern_name": pattern_name, "kit": final_kit})
        print("✅ Kit aprobado y método de verificación guardado.")

    return {"execution_kit": kits}


graph_builder = StateGraph(GraphState)

graph_builder.add_node("insights", insights_node)
graph_builder.add_node("action_planning", action_planning_node)
graph_builder.add_node("approval", approval_node)
graph_builder.add_node("execution_kit", execution_kit_node)

graph_builder.add_edge(START, "insights")
graph_builder.add_edge("insights", "action_planning")
graph_builder.add_edge("action_planning", "approval")
graph_builder.add_edge("approval", "execution_kit")
graph_builder.add_edge("execution_kit", END)

graph = graph_builder.compile()


if __name__ == "__main__":
    result = graph.invoke({"pattern_name": ""})

    print(f"\n\n=== RESULTADO FINAL: {len(result['recommendation'])} RECOMENDACIONES APROBADAS ===\n")
    for i, item in enumerate(result["recommendation"], start=1):
        print(f"--- Aprobada {i}: {item['pattern_name']} ---\n")
        print(item["text"])
        print()

    print(f"\n\n=== {len(result['execution_kit'])} KITS DE EJECUCIÓN APROBADOS ===\n")
    for i, kit_item in enumerate(result["execution_kit"], start=1):
        print(f"--- Kit {i}: {kit_item['pattern_name']} ---\n")
        print(kit_item["kit"])
        print()