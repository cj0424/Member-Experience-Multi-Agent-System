"""
Action Planning Agent — takes a confirmed pattern from Insights
and produces a practical, well-reasoned recommendation: the
problem, real options (with cost tradeoffs when relevant), and
why it's worth the club's time — structured for quick scanning,
written like a person talking, not a formal corporate template.

Also supports revision: if the owner rejects or asks to change a
recommendation, run_action_planning_revision() produces a genuinely
new attempt informed by their specific feedback, not a reworded
repeat.
"""

import os
import glob
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def load_rag_library(folder_path: str) -> str:
    """Reads every document in the RAG library folder, labeled by
    source file, so Gemini judges relevance itself."""
    combined = []
    for filepath in sorted(glob.glob(f"{folder_path}/*.txt")):
        filename = os.path.basename(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        combined.append(f"--- FUENTE: {filename} ---\n{content}")
    return "\n\n".join(combined)


def build_prompt(pattern_description: str, rag_context: str) -> str:
    """General-purpose prompt — no hardcoded topic. Applies the
    same reasoning template to any pattern Insights Agent finds."""
    return f"""Eres un asistente que ayuda al propietario de un club de pádel
independiente en Madrid a decidir qué hacer con un patrón real detectado
en las reseñas de sus socios. Escribe como si le hablaras directamente
al propietario — claro, directo y práctico, sin lenguaje de consultoría
corporativa.

PATRÓN CONFIRMADO:
{pattern_description}

BIBLIOTECA DE DOCUMENTOS DE REFERENCIA:
{rag_context}

SUPUESTOS DE ESCALA (genéricos, no son datos reales de este club
específico — úsalos solo para calibrar la proporción de tu
recomendación): un club de pádel independiente de tamaño medio en
Madrid suele operar con márgenes ajustados y presupuestos de
mantenimiento limitados.

Estructura tu recomendación en TRES partes claras, cada una con un
título breve que tú mismo elijas según el patrón (por ejemplo "El
problema", "Qué se puede hacer", "Por qué vale la pena" — adapta el
título a lo que tenga sentido para este caso):

1. El problema — en 1-2 frases, qué está pasando según la evidencia.
2. Qué se puede hacer — si el esfuerzo es Medio o Alto, presenta 2
   opciones con distinto nivel de coste, en formato de lista
   numerada. Si el esfuerzo es Bajo, basta una sola opción clara.
3. Por qué vale la pena para el club — en 1-2 frases, una ventaja
   real y concreta (retención, ocupación, reputación), no solo
   "los socios estarán contentos".

Reglas:
- Basa la solución técnica en la biblioteca de referencia si algún
  documento aplica realmente (cítalo por su nombre); si ninguno
  aplica, dilo explícitamente y usa buenas prácticas generales.
- No hagas afirmaciones médicas o de seguridad (ej. riesgo de
  lesión) a menos que estén directamente respaldadas por la
  evidencia de las reseñas o por un documento de la biblioteca.
- Sé realista y proporcional a la escala descrita arriba.
- Usa lenguaje natural y directo dentro de cada parte, pero
  mantén las tres partes visualmente separadas para que se pueda
  escanear rápido.

Después de las tres partes, añade solo estos tres datos, de forma breve:

⏱️ Esfuerzo: [Bajo/Medio/Alto]
📚 Fuente: [documento citado, o "buenas prácticas generales"]
🟢/🟡/🔴 Confianza: [Alto/Moderado/Bajo]

Ahora escribe la recomendación real para el patrón indicado."""


def build_revision_prompt(pattern_description: str, rag_context: str,
                           previous_recommendation: str, owner_feedback: str) -> str:
    """Produces a genuinely revised recommendation, informed by
    what the owner specifically didn't like about the first one —
    not just a reworded repeat."""
    return f"""Eres un asistente que ayuda al propietario de un club de pádel
independiente en Madrid. Ya propusiste una recomendación anterior para
un patrón real, pero el propietario la ha rechazado o pedido cambios.

PATRÓN CONFIRMADO:
{pattern_description}

BIBLIOTECA DE DOCUMENTOS DE REFERENCIA:
{rag_context}

RECOMENDACIÓN ANTERIOR (rechazada o a modificar):
{previous_recommendation}

FEEDBACK DEL PROPIETARIO:
{owner_feedback}

Tu tarea: genera una NUEVA recomendación que responda directamente al
feedback del propietario — no repitas la anterior con otras palabras.
Si pide algo más económico, ofrece opciones genuinamente más baratas.
Si dice que no le convence el enfoque, propón una dirección distinta,
no una variación cosmética de la misma idea.

Antes de la recomendación revisada, añade una línea breve:
"✏️ Cambios respecto a tu feedback: [resumen de 1 frase de qué cambió
específicamente]" — así el propietario puede verificar rápidamente si
su comentario fue realmente incorporado.

Después, sigue la misma estructura y reglas que una recomendación
normal: el problema (puedes resumirlo brevemente ya que no es nuevo),
qué se puede hacer ahora (ajustado al feedback), y por qué vale la
pena. Incluye también ⏱️ Esfuerzo, 📚 Fuente, y 🟢/🟡/🔴 Confianza al final.

Ahora escribe la recomendación revisada."""


def run_action_planning_agent(pattern_description: str, rag_folder: str):
    """First-pass recommendation for a confirmed pattern."""
    rag_context = load_rag_library(rag_folder)
    prompt = build_prompt(pattern_description, rag_context)

    response = client.models.generate_content(
        model="gemini-3.7-flash",
        contents=prompt
    )
    return response.text


def run_action_planning_revision(pattern_description: str, rag_folder: str,
                                   previous_recommendation: str, owner_feedback: str):
    """Revised recommendation, informed by specific owner feedback
    on a previously rejected or unsatisfactory recommendation."""
    rag_context = load_rag_library(rag_folder)
    prompt = build_revision_prompt(
        pattern_description, rag_context, previous_recommendation, owner_feedback
    )

    response = client.models.generate_content(
        model="gemini-3.7-flash",
        contents=prompt
    )
    return response.text


if __name__ == "__main__":
    test_pattern = """Problemas de aislamiento térmico y climatización
Evidencia: 4 reseñas (REV-016, REV-017, REV-018, REV-027)
Confianza: Moderado"""

    print("=== PRIMERA RECOMENDACIÓN ===\n")
    first_result = run_action_planning_agent(test_pattern, "data/rag_library")
    print(first_result)

    print("\n\n=== RECOMENDACIÓN REVISADA (tras feedback del propietario) ===\n")
    feedback = "Las dos opciones son demasiado caras para nosotros ahora mismo, necesitamos algo de coste muy bajo aunque sea una solución temporal."

    revised_result = run_action_planning_revision(
        test_pattern, "data/rag_library", first_result, feedback
    )
    print(revised_result)