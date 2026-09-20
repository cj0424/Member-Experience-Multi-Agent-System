"""
Outcome Check Agent — a continuity chain, not a report. Sequential
gates, each fully evaluated before the next: (1) was it actually
executed, checked against Execution Kit Agent's own verification
method; (2) has enough time genuinely passed, reasoned freely per
this specific action, no fixed category table; (3) only then, ALL
available secondary evidence (relevant reviews AND rating trend)
is synthesized together — never a single signal read in isolation.

Four possible outcomes:
- FLAG DE IMPLEMENTACIÓN — execution not confirmed
- CONTINUAR — too early to judge
- CERRAR — strategy worked
- PIVOTAR — tried in good faith, no clear result, worsened, or
  contradictory signals (mixed evidence is never enough to close)

Reads/writes real pattern data via Supabase — unlike Agents 1-3,
this agent's job spans real time gaps between check-ins, which
in-memory data flow alone can't handle.
"""

import os
from dotenv import load_dotenv
from google import genai
from supabase import create_client

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)


def get_pattern_from_db(pattern_name: str) -> dict:
    """Reads a pattern's real stored data from Supabase, instead
    of using manually-typed test values."""
    result = supabase.table("patterns").select("*").eq("pattern_name", pattern_name).execute()
    if not result.data:
        raise ValueError(f"No pattern found in database named: {pattern_name}")
    return result.data[0]


def update_pattern_in_db(pattern_name: str, updates: dict):
    """Updates a pattern's stored data after a check runs — e.g.
    incrementing cycles_since_approval, changing status."""
    supabase.table("patterns").update(updates).eq("pattern_name", pattern_name).execute()


def build_prompt(pattern_name: str, verification_method: str, verification_result: str,
                  action_description: str, cycles_since_approval: int,
                  new_reviews_since_approval: str = "Ninguna",
                  rating_before: str = "No disponible", rating_after: str = "No disponible") -> str:
    return f"""Eres el agente de continuidad de un sistema que ayuda a un club
de pádel a decidir, de forma disciplinada, qué hacer después de aprobar
y ejecutar una acción sobre un patrón real. Tu decisión afecta
directamente si el club sigue esperando sin necesidad, o actúa cuando
realmente corresponde — por eso debes razonar paso a paso, sin
saltarte ninguno.

PATRÓN: {pattern_name}
ACCIÓN APROBADA Y EJECUTADA: {action_description}
CICLOS TRANSCURRIDOS: {cycles_since_approval}

MÉTODO DE VERIFICACIÓN (del kit de ejecución ya aprobado — única
base válida para saber si la acción se ejecutó):
{verification_method}
RESULTADO REPORTADO: {verification_result}

RESEÑAS NUEVAS DESDE LA APROBACIÓN:
{new_reviews_since_approval}

VALORACIÓN MEDIA — antes: {rating_before} / después: {rating_after}

Sigue este proceso EN ORDEN ESTRICTO — cada paso solo se evalúa si
el anterior lo permite:

PASO 1: ¿El resultado de verificación confirma que la acción se
ejecutó? Considera tres posibilidades:
- Confirmado claramente → continúa al Paso 2.
- No confirmado / sin ejecutar → Decisión final: FLAG DE
  IMPLEMENTACIÓN. No sigas más — sin ejecución real, cualquier
  evidencia externa sería sobre otra cosa, no sobre esta acción.
- Ambiguo o parcial (ejecución incompleta, verificación informal
  sin registro claro) → Decisión final: FLAG DE IMPLEMENTACIÓN,
  indicando explícitamente "verificación poco clara, requiere
  confirmación directa" en vez de "no ejecutado".

PASO 2 (dado que el Paso 1 confirmó ejecución): Razona TÚ MISMO,
según la naturaleza específica de ESTA acción — no existen
categorías fijas. ¿Es algo que se notaría casi de inmediato, o
necesita tiempo real de uso o condiciones específicas para mostrar
efecto genuino? Explica tu razonamiento antes de decidir.
- Si NO ha pasado tiempo suficiente → Decisión final: CONTINUAR.
  No sigas más.
- Si SÍ → continúa al Paso 3.

PASO 3 (dado que la ejecución fue confirmada y ya pasó tiempo
suficiente): Reúne TODA la evidencia externa disponible — reseñas
relevantes Y valoración media, nunca una sola por separado.
Descarta explícitamente cualquier reseña que no mencione directa y
específicamente este patrón.

Razona de forma CONJUNTA: ¿las señales disponibles apuntan en la
misma dirección, se contradicen, o no hay suficiente de ninguna?
Una sola reseña relevante es una señal débil sola, pero más
convincente si la valoración también mejoró en el mismo periodo.
Ninguna señal externa disponible no es neutral — es ausencia real
de confirmación.

Decide:
- Señales coincidiendo en positivo, evidencia sólida (2+ reseñas
  relevantes positivas, o 1 reseña + valoración que mejora) →
  CERRAR
- Una sola señal positiva débil, sin refuerzo de la otra →
  CONTINUAR (explica por qué es aún una señal temprana, no
  confirmada)
- Señales que se contradicen entre sí (ej. una reseña relevante
  positiva y otra negativa, o una reseña positiva pero la
  valoración baja) → PIVOTAR, explicando la contradicción
  específica — evidencia mixta no es suficiente para cerrar como
  resuelto.
- Ninguna señal externa relevante, o todas las señales apuntan a
  empeoramiento → PIVOTAR

Formato:

🔁 CONTINUIDAD — [patrón] (ciclo {cycles_since_approval})

Paso 1: [...]
Paso 2: [tu razonamiento sobre el tiempo necesario]
Paso 3: [síntesis conjunta de reseñas relevantes + valoración, si aplica]

Decisión: [🚩 FLAG DE IMPLEMENTACIÓN / 🔵 CONTINUAR / 🟢 CERRAR / 🟠 PIVOTAR]

➡️ Siguiente paso concreto: [específico; si PIVOTAR, incluye una
hipótesis concreta de por qué no funcionó]

Ahora razona y decide el caso real indicado."""


def run_outcome_check_agent(pattern_name: str, verification_method: str, verification_result: str,
                              action_description: str, cycles_since_approval: int,
                              new_reviews_since_approval: str = "Ninguna",
                              rating_before: str = "No disponible", rating_after: str = "No disponible"):
    prompt = build_prompt(pattern_name, verification_method, verification_result,
                           action_description, cycles_since_approval,
                           new_reviews_since_approval, rating_before, rating_after)
    response = client.models.generate_content(model="gemini-3.7-flash", contents=prompt)
    return response.text


def run_outcome_check_from_db(pattern_name: str,
                                new_reviews_since_approval: str = "Ninguna",
                                rating_before: str = "No disponible",
                                rating_after: str = "No disponible"):
    """Real-use version: pulls the pattern's stored data from
    Supabase automatically, instead of requiring every field to
    be typed in manually. Reviews and ratings still come in as
    parameters, since those come from a separate live source
    (Google API, Phase 2) — not from this table."""
    pattern_data = get_pattern_from_db(pattern_name)

    result = run_outcome_check_agent(
        pattern_name=pattern_data["pattern_name"],
        verification_method=pattern_data["verification_method"],
        verification_result=pattern_data["verification_result"],
        action_description=pattern_data["approved_action"],
        cycles_since_approval=pattern_data["cycles_since_approval"],
        new_reviews_since_approval=new_reviews_since_approval,
        rating_before=rating_before,
        rating_after=rating_after
    )

    return result


if __name__ == "__main__":
    print("=== PRUEBA REAL: leyendo desde Supabase ===\n")
    result = run_outcome_check_from_db(
        "Exceso de arena en las pistas",
        new_reviews_since_approval="""Socio-Z: "Las pistas ya no tienen tanta arena, se nota la mejora.\"""",
        rating_before="4.2", rating_after="4.4"
    )
    print(result)