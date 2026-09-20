"""
Action Planning Agent — takes a confirmed pattern from Insights
and produces a specific, grounded action plan.
"""

import os
import glob
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def load_rag_library(folder_path: str) -> str:
    """Reads every document in the RAG library folder and combines
    them, clearly labeled by source file, so Gemini can judge
    relevance itself rather than being handed one pre-chosen file."""
    combined = []
    for filepath in sorted(glob.glob(f"{folder_path}/*.txt")):
        filename = os.path.basename(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        combined.append(f"--- FUENTE: {filename} ---\n{content}")
    return "\n\n".join(combined)


def build_prompt(pattern_description: str, rag_context: str) -> str:
    """Builds the prompt for generating a grounded action plan."""
    return f"""Eres un asistente que ayuda a un club de pádel a planificar
una respuesta a un patrón real identificado en las reseñas de sus socios.

PATRÓN CONFIRMADO:
{pattern_description}

BIBLIOTECA DE DOCUMENTOS DE REFERENCIA (varios documentos, separados
por "--- FUENTE: ---"). Revisa cuál, si alguno, es realmente relevante
para este patrón específico. Si ninguno lo es, dilo explícitamente y
usa buenas prácticas generales en su lugar — nunca cites un documento
que no trate directamente el tema del patrón:

{rag_context}

Tu tarea:
1. Propón un plan de acción específico y concreto para abordar este patrón.
2. Indica claramente si tu recomendación está basada en uno de los
   documentos de la biblioteca (cita el nombre exacto del archivo) o
   en buenas prácticas generales (dilo explícitamente).
3. Indica el esfuerzo estimado (bajo/medio/alto) y tu nivel de confianza.
4. Sé breve y directo — máximo 6-8 líneas de recomendación real.

Sigue este formato:

💡 PLAN — [nombre corto del plan]
📝 Pasos: [1-3 pasos concretos]
⏱️ Esfuerzo: [Bajo/Medio/Alto]
📚 Fuente: [nombre del archivo citado, o "buenas prácticas generales, sin
   fuente oficial específica"]
🟢/🟡/🔴 Confianza: [Alto/Moderado/Bajo]

Ejemplo de un plan bien formado:

💡 PLAN — Redistribución semanal de arena en pistas
📝 Pasos: 1) Redistribuir arena semanalmente con cepillo específico,
2) Verificar nivel de arena tras cada redistribución, 3) Descompactación
completa dos veces al año.
⏱️ Esfuerzo: Bajo
📚 Fuente: sevilla_court_maintenance.txt
🟢 Confianza: Alto

Ahora aplica este mismo formato al plan real para el patrón indicado."""


def run_action_planning_agent(pattern_description: str, rag_folder: str):
    rag_context = load_rag_library(rag_folder)
    prompt = build_prompt(pattern_description, rag_context)

    response = client.models.generate_content(
        model="gemini-3.7-flash",
        contents=prompt
    )
    return response.text


if __name__ == "__main__":
    # Testing with the temperature pattern — this one should NOT match
    # any of the 3 RAG files, proving Gemini correctly says so instead
    # of forcing a false citation
    test_pattern = """Problemas de aislamiento térmico y climatización
Evidencia: 4 reseñas (REV-016, REV-017, REV-018, REV-027)
Confianza: Moderado"""

    result = run_action_planning_agent(
        test_pattern,
        "data/rag_library"
    )
    print(result)