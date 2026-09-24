"""
Action Planning Agent — takes a confirmed pattern and produces a
practical, well-reasoned recommendation: the problem, real options
(with cost tradeoffs when relevant), and why it's worth the club's
time — structured for quick scanning, written like a person
talking, not a formal corporate template.

Three entry points, sharing one SHARED_RULES block so every prompt
sent to Gemini is fully self-contained (no path relies on rules
defined only elsewhere — each API call is stateless), while the
rules only need to be edited in one place:
- run_action_planning_agent: first-pass recommendation for a
  brand-new confirmed pattern.
- run_action_planning_revision: owner rejected a proposal BEFORE
  trying it (e.g. too expensive) — revises based on their stated
  preference.
- run_action_planning_from_pivot: a previous action WAS actually
  tried and verified, but Outcome Check Agent found no real result
  (Pivotar) — real-world evidence, not a preference, so it gets a
  genuinely different approach, not a cosmetic variation. Now
  accepts rejected_ideas, so a previously-discarded idea never
  silently resurfaces — a real limitation of stateless LLM calls,
  fixed by passing the relevant history back in explicitly.
"""

import os
import glob
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


SHARED_RULES = """Reglas:
- Basa la solución técnica en la biblioteca de referencia si algún
  documento aplica realmente (cítalo por su nombre); si ninguno
  aplica, dilo explícitamente y usa buenas prácticas generales.

- La biblioteca puede incluir un documento de fidelización/retención,
  distinto de los documentos técnicos. Para TODO patrón, sin
  excepción, sigue estos dos pasos EN ORDEN:
  PASO 1 — Evalúa: ¿el documento de fidelización/retención podría
  aportar algo útil aquí? Esto es obligatorio para todos los
  patrones, no solo los de satisfacción general.
  PASO 2 — Según lo que concluyas en el Paso 1, escribe una línea
  breve mostrando tu conclusión, usando uno de estos tres casos:
    (a) USAR COMO PRINCIPAL — el patrón es de satisfacción general
        sin un problema concreto que resolver, así que el documento
        de fidelización es la base de la recomendación.
    (b) USAR COMO COMPLEMENTO — hay un problema real que resolver,
        pero una táctica de fidelización aporta valor genuino
        mientras se soluciona. Antes de incluirla, comprueba: ¿esta
        táctica añadiría más presión sobre el mismo recurso o
        limitación que causa el problema (ej. más gente en un
        espacio ya con capacidad ajustada)? Si es así, ajusta la
        táctica para evitarlo (ej. limitarla a una franja horaria
        con menos presión) en vez de descartarla directamente.
    (c) NO APLICA — el documento no aporta nada útil a este
        problema concreto. Dilo en una frase y sigue adelante sin
        forzarlo.
  Esta línea de conclusión debe aparecer SIEMPRE en tu respuesta,
  igual que ya haces con los riesgos ("Ojo con...") — nunca la
  omitas, incluso si la conclusión es (c).
  La fidelización NUNCA sustituye la acción correctiva real de un
  problema — solo puede complementarla.

- Antes de proponer cualquier acción, razona si podría chocar con
  algo que ya sabes de este club a partir de la evidencia real
  disponible — nunca una suposición inventada.

- Cualquier acción que implique seguimiento individual y continuo
  de socios debe ser genuinamente realista para un club
  independiente de una sola sede con personal limitado — prefiere
  medidas simples y puntuales sobre las que requieran seguimiento
  manual constante de cada socio.

- No hagas afirmaciones médicas o de seguridad a menos que estén
  directamente respaldadas por evidencia real.

- Antes de la recomendación final, piensa si podría causar un
  efecto secundario no deseado (ej. reducir ventilación al sellar
  accesos, generar ruido, afectar otra parte de la experiencia).
  Si identificas un riesgo plausible y real, menciónalo en una
  línea breve, y prefiere una alternativa igualmente efectiva con
  menos riesgo si existe. No inventes riesgos improbables solo
  para parecer cauteloso.

- Sé realista y proporcional a la escala descrita arriba."""


CLOSING_FORMAT = """Termina con:
⏱️ Esfuerzo: [Bajo/Medio/Alto]
📚 Fuente: [documento citado, o "buenas prácticas generales"]
🟢/🟡/🔴 Confianza: [Alto/Moderado/Bajo]"""


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
    """First-pass recommendation for a brand-new pattern. No
    hardcoded topic — applies the same template to any pattern."""
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
problema", "Qué se puede hacer", "Por qué vale la pena"):

1. El problema — en 1-2 frases, qué está pasando según la evidencia.
2. Qué se puede hacer — si el esfuerzo es Medio o Alto, presenta 2
   opciones con distinto nivel de coste, en formato de lista
   numerada. Si el esfuerzo es Bajo, basta una sola opción clara.
3. Por qué vale la pena para el club — en 1-2 frases, una ventaja
   real y concreta (retención, ocupación, reputación).

{SHARED_RULES}
- Usa lenguaje natural y directo, pero mantén las tres partes
  visualmente separadas para que se pueda escanear rápido.

{CLOSING_FORMAT}

Ahora escribe la recomendación real para el patrón indicado."""


def build_revision_prompt(pattern_description: str, rag_context: str,
                           previous_recommendation: str, owner_feedback: str) -> str:
    """Revision when the owner rejects a proposal BEFORE trying it
    (a stated preference, e.g. cost)."""
    return f"""Eres un asistente que ayuda al propietario de un club de pádel
independiente en Madrid a decidir qué hacer con un patrón real. Escribe
como si le hablaras directamente al propietario — claro, directo y
práctico, sin lenguaje de consultoría corporativa.

Ya propusiste una recomendación anterior para un patrón real, pero el
propietario la ha rechazado o pedido cambios.

PATRÓN CONFIRMADO:
{pattern_description}

BIBLIOTECA DE DOCUMENTOS DE REFERENCIA:
{rag_context}

SUPUESTOS DE ESCALA (genéricos, no son datos reales de este club
específico): un club de pádel independiente de tamaño medio en Madrid
suele operar con márgenes ajustados y presupuestos de mantenimiento
limitados.

RECOMENDACIÓN ANTERIOR (rechazada o a modificar):
{previous_recommendation}

FEEDBACK DEL PROPIETARIO:
{owner_feedback}

Tu tarea: genera una NUEVA recomendación que responda directamente al
feedback del propietario — no repitas la anterior con otras palabras.
Si pide algo más económico, ofrece opciones genuinamente más baratas.
Si dice que no le convence el enfoque, propón una dirección distinta.

Primero, en una línea:
"✏️ Cambios respecto a tu feedback: [resumen de 1 frase]"

Después, estructura tu recomendación revisada en TRES partes claras
(mismos títulos flexibles que una recomendación normal).

{SHARED_RULES}

{CLOSING_FORMAT}

Ahora escribe la recomendación revisada."""


def build_from_pivot_prompt(pattern_description: str, rag_context: str,
                              previous_action: str, outcome_evidence: str,
                              rejected_ideas: str = "Ninguna") -> str:
    """New recommendation when a previous action was actually
    tried and verified, but showed no real result (Pivotar). Now
    includes rejected_ideas, so an idea the owner already discarded
    doesn't silently resurface — the LLM call is stateless, so this
    history has to be passed in explicitly every time."""
    return f"""Eres un asistente que ayuda al propietario de un club de pádel
independiente en Madrid a decidir qué hacer con un patrón real. Escribe
como si le hablaras directamente al propietario — claro, directo y
práctico, sin lenguaje de consultoría corporativa.

Ya se aprobó, ejecutó y verificó una acción anterior sobre este patrón,
pero no mostró ningún resultado real tras un intento genuino y con
tiempo suficiente. No hay evidencia de que la acción anterior haya
causado daño, solo que no fue suficiente.

PATRÓN: {pattern_description}

BIBLIOTECA DE DOCUMENTOS DE REFERENCIA:
{rag_context}

SUPUESTOS DE ESCALA (genéricos, no son datos reales de este club
específico): un club de pádel independiente de tamaño medio en Madrid
suele operar con márgenes ajustados y presupuestos de mantenimiento
limitados.

ACCIÓN ANTERIOR YA INTENTADA:
{previous_action}

EVIDENCIA REAL DEL RESULTADO:
{outcome_evidence}

IDEAS YA DESCARTADAS POR EL PROPIETARIO — NUNCA LAS REPITAS NI LAS
REFORMULES DE FORMA SIMILAR, AUNQUE PAREZCAN ENCAJAR:
{rejected_ideas}

Propón un enfoque GENUINAMENTE DISTINTO al anterior, no una
variación cosmética de la misma idea, y que tampoco coincida con
ninguna idea ya descartada arriba.

Primero, en una línea:
"📊 Por qué el enfoque anterior no fue suficiente: [1 frase]"

Después, estructura tu recomendación en TRES partes claras (mismos
títulos flexibles que una recomendación normal).

{SHARED_RULES}

{CLOSING_FORMAT}

Ahora escribe la recomendación real para esta situación."""


def run_action_planning_agent(pattern_description: str, rag_folder: str = "data/rag_library"):
    """First-pass recommendation for a brand-new confirmed pattern."""
    rag_context = load_rag_library(rag_folder)
    prompt = build_prompt(pattern_description, rag_context)
    response = client.models.generate_content(model="gemini-3.7-flash", contents=prompt)
    return response.text


def run_action_planning_revision(pattern_description: str, rag_folder: str,
                                   previous_recommendation: str, owner_feedback: str):
    """Revision when the owner rejects a proposal before trying it."""
    rag_context = load_rag_library(rag_folder)
    prompt = build_revision_prompt(pattern_description, rag_context,
                                     previous_recommendation, owner_feedback)
    response = client.models.generate_content(model="gemini-3.7-flash", contents=prompt)
    return response.text


def run_action_planning_from_pivot(pattern_description: str, rag_folder: str,
                                     previous_action: str, outcome_evidence: str,
                                     rejected_ideas: str = "Ninguna"):
    """New recommendation after Outcome Check Agent returns Pivotar
    — a previously tried, verified action showed no real result.
    rejected_ideas carries forward anything the owner has already
    explicitly turned down for this pattern, across separate,
    stateless calls."""
    rag_context = load_rag_library(rag_folder)
    prompt = build_from_pivot_prompt(pattern_description, rag_context,
                                       previous_action, outcome_evidence,
                                       rejected_ideas)
    response = client.models.generate_content(model="gemini-3.7-flash", contents=prompt)
    return response.text


if __name__ == "__main__":
    # Standalone test entry point — normally this agent is called
    # by graph.py or continuity_graph.py with a real pattern.
    # Replace test_pattern below only if testing this file in isolation.
    test_pattern = """[Pega aquí un patrón real de Insights Agent para
probar este archivo de forma aislada]"""

    print("=== PRUEBA AISLADA DE ACTION PLANNING AGENT ===\n")
    result = run_action_planning_agent(test_pattern)
    print(result)