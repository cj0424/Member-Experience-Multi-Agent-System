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

Every prompt receives the shared RAG library (rag.py): the technical
references it can cite, plus the club profile — how this club actually
works — so recommendations fit the club, not a generic one.

Phase 3: the plan no longer has to write a verdict on the loyalty guide
for every pattern (it was "no aplica" for almost every practical problem).
Any library document — loyalty guide included — is used only when it
really applies, and the "Fuente" line says which one and what it added.
"""

from rag import load_rag_library, load_club_profile
from llm import generate


SHARED_RULES = """Reglas:
- Usa un documento de la biblioteca de referencia SOLO si aplica de
  verdad a este patrón, y cítalo en "Fuente" por su nombre junto con
  lo que aporta (por ejemplo, "Normas de conservación de pistas —
  frecuencia y método de cepillado"). Si ninguno aplica, en "Fuente"
  pon "buenas prácticas generales". No escribas ninguna línea sobre
  documentos que NO aplican.

- La biblioteca incluye un documento de fidelización/retención.
  Úsalo solo cuando aporte algo real: como base, si el patrón es de
  satisfacción general sin un problema concreto que resolver; o como
  complemento, si una táctica de fidelización ayuda mientras se
  resuelve un problema real sin añadir presión sobre lo que lo causa
  (por ejemplo, más gente en un espacio que ya se llena). Nunca
  sustituye la acción correctiva real.

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

- Sé realista y proporcional a la escala descrita arriba.

- Antes de cerrar la recomendación, comprueba tres cosas y corrige lo
  que falle: que cada acción cabe en los turnos y la carga del
  personal que indica el PERFIL DEL CLUB; que no pide esfuerzos a los
  socios para resolver un problema del club; y que, si algo depende
  de la estación o de una situación temporal, dice hasta cuándo se
  aplica.

- Escribe en español de España (por ejemplo, "comunicar" o "indicar"
  en vez de "reportar"), dirigiéndote al propietario con el
  tratamiento que indica el PERFIL DEL CLUB (tú o usted).

- Usa el PERFIL DEL CLUB para que la recomendación encaje con cómo
  funciona de verdad este club (personal y turnos, normas, canales,
  herramientas, presupuesto y quién aprueba qué). No lo cites como
  Fuente. Lo marcado "por confirmar" no lo des por hecho.

- En cada bullet, pon en **negrita** solo la acción clave (3-6
  palabras). En la parte 3, pon en **negrita** la ventaja principal.
  Nunca pongas en negrita una frase completa."""


CLOSING_FORMAT = """Termina con:
⏱️ **Esfuerzo:** [Bajo/Medio/Alto]
📚 **Fuente:** [documento citado — qué aporta, en pocas palabras; o "buenas prácticas generales"]
🟢/🟡/🔴 **Confianza:** [Alto/Moderado/Bajo]"""


def build_prompt(pattern_description: str, rag_context: str, club_profile: str) -> str:
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

PERFIL DEL CLUB (contexto interno, no citable como Fuente):
{club_profile}

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


def build_revision_prompt(pattern_description: str, rag_context: str, club_profile: str,
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

PERFIL DEL CLUB (contexto interno, no citable como Fuente):
{club_profile}

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


def build_from_pivot_prompt(pattern_description: str, rag_context: str, club_profile: str,
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

PERFIL DEL CLUB (contexto interno, no citable como Fuente):
{club_profile}

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
    prompt = build_prompt(pattern_description, rag_context, load_club_profile(rag_folder))
    return generate(prompt, agent="action_planning")


def run_action_planning_revision(pattern_description: str, rag_folder: str,
                                   previous_recommendation: str, owner_feedback: str):
    """Revision when the owner rejects a proposal before trying it."""
    rag_context = load_rag_library(rag_folder)
    prompt = build_revision_prompt(pattern_description, rag_context, load_club_profile(rag_folder),
                                     previous_recommendation, owner_feedback)
    return generate(prompt, agent="action_planning")


def run_action_planning_from_pivot(pattern_description: str, rag_folder: str,
                                     previous_action: str, outcome_evidence: str,
                                     rejected_ideas: str = "Ninguna"):
    """New recommendation after Outcome Check Agent returns Pivotar
    — a previously tried, verified action showed no real result.
    rejected_ideas carries forward anything the owner has already
    explicitly turned down for this pattern, across separate,
    stateless calls."""
    rag_context = load_rag_library(rag_folder)
    prompt = build_from_pivot_prompt(pattern_description, rag_context, load_club_profile(rag_folder),
                                       previous_action, outcome_evidence,
                                       rejected_ideas)
    return generate(prompt, agent="action_planning")


if __name__ == "__main__":
    # Standalone test entry point — normally this agent is called
    # by graph.py or continuity_graph.py with a real pattern.
    # Replace test_pattern below only if testing this file in isolation.
    test_pattern = """[Pega aquí un patrón real de Insights Agent para
probar este archivo de forma aislada]"""

    print("=== PRUEBA AISLADA DE ACTION PLANNING AGENT ===\n")
    result = run_action_planning_agent(test_pattern)
    print(result)
