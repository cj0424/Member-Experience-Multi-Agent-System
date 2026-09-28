"""
Outcome Check Agent — a continuity chain, not a report. Five
sequential steps, each fully evaluated before the next:
(1) was it actually executed, with real, tiered evidence;
(2) has enough real time passed — reasoned freely per pattern,
covering BOTH a first genuine sign of effect AND enough time to
trust the problem hasn't quietly recurred, never a fixed universal
number of cycles;
(3) define a success criterion specific to THIS pattern, before
looking at any effectiveness evidence;
(4) gather all available effectiveness evidence — reviews, rating,
and direct human confirmation about the RESULT (separate from
Paso 1's execution evidence);
(5) compare that evidence against the Paso 3 criterion and decide.

Four possible outcomes:
- FLAG DE IMPLEMENTACIÓN — execution not confirmed, or evidence too weak
- CONTINUAR — too early to judge, or a genuinely promising early
  sign that hasn't yet had time to prove it's sustained
- CERRAR — strategy worked, sustained long enough to trust it,
  told as a clear before/after story
- PIVOTAR — didn't work, told as a clear story of why, with a
  specific hypothesis for the next attempt

Reads/writes real pattern data via Supabase — unlike Agents 1-3,
this agent's job spans real time gaps between check-ins, which
in-memory data flow alone can't handle.

Also receives the club profile from the shared RAG library (rag.py),
so it judges evidence, responsibilities and timing against how this
club actually works (e.g. who can realistically verify what, and when).
"""

import os
from dotenv import load_dotenv
from google import genai
from supabase import create_client
from rag import load_club_profile

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)


def get_pattern_from_db(pattern_name: str) -> dict:
    """Reads a pattern's real stored data from Supabase."""
    result = supabase.table("patterns").select("*").eq("pattern_name", pattern_name).execute()
    if not result.data:
        raise ValueError(f"No pattern found in database named: {pattern_name}")
    return result.data[0]


def update_pattern_in_db(pattern_name: str, updates: dict):
    """Updates a pattern's stored data after a check runs."""
    supabase.table("patterns").update(updates).eq("pattern_name", pattern_name).execute()


def build_prompt(pattern_name: str, verification_method: str, verification_result: str,
                  action_description: str, cycles_since_approval: int,
                  new_reviews_since_approval: str = "Ninguna",
                  rating_before: str = "No disponible", rating_after: str = "No disponible",
                  club_profile: str = "No disponible.") -> str:
    return f"""Eres el agente de continuidad de un sistema que ayuda a un club
de pádel a decidir, de forma disciplinada, qué hacer después de aprobar
y ejecutar una acción sobre un patrón real. Tu decisión afecta
directamente si el club sigue esperando sin necesidad, o actúa cuando
realmente corresponde — por eso debes razonar paso a paso, sin
saltarte ninguno, y cada paso solo se evalúa si el anterior lo permite.

Escribe en español de España, claro y directo, dirigiéndote al
propietario con el tratamiento que indica el PERFIL DEL CLUB (tú o
usted). Frases cortas, sin gerundios encadenados ni lenguaje
administrativo o de consultoría, y sin tecnicismos innecesarios (por
ejemplo, "comunicado" o "indicado" en vez de "reportado").

PATRÓN: {pattern_name}
ACCIÓN APROBADA Y EJECUTADA: {action_description}
CICLOS TRANSCURRIDOS DESDE LA APROBACIÓN: {cycles_since_approval}

MÉTODO DE VERIFICACIÓN ACORDADO (del kit de ejecución ya aprobado):
{verification_method}

LO QUE EL PROPIETARIO HA INDICADO SOBRE LA EJECUCIÓN (incluye el nivel de
evidencia disponible):
{verification_result}

RESEÑAS, COMENTARIOS O CONFIRMACIONES DIRECTAS SOBRE SI EL PROBLEMA
ORIGINAL MEJORÓ, DESDE LA APROBACIÓN:
{new_reviews_since_approval}

VALORACIÓN MEDIA — antes: {rating_before} / después: {rating_after}

PERFIL DEL CLUB (contexto interno: úsalo para valorar si la evidencia,
los responsables y los plazos son realistas para este club — por
ejemplo, quién puede comprobar algo y en qué turno. No lo cites):
{club_profile}

---

PASO 1 — ¿Se ejecutó realmente la acción? Evalúa el nivel de
evidencia en lo que ha indicado el propietario:
- Nivel ALTO: un registro real, con fecha, responsable y firma (ej.
  un tracker completado).
- Nivel MEDIO: una observación directa y específica del propietario
  (algo concreto que comprobó personalmente, no una impresión vaga).
- Nivel BAJO: un relato verbal de lo que el personal dijo, sin
  ningún registro que lo respalde.
Un nivel ALTO o MEDIO cuenta como ejecución confirmada — continúa al
Paso 2. Un nivel BAJO, o la ausencia total de evidencia, se trata
como NO confirmado.
- No confirmado, o evidencia insuficiente según lo anterior →
  Decisión final: FLAG DE IMPLEMENTACIÓN, indicando qué tipo de
  evidencia más sólida se necesitaría. No sigas más.

PASO 2 (dado que el Paso 1 confirmó ejecución con evidencia
suficiente): Razona TÚ MISMO, según la naturaleza específica de ESTA
acción — no existen categorías fijas ni un número universal de
ciclos — cuánto tiempo real necesitaría para: (a) mostrar un primer
efecto genuino, Y (b) confirmar que el problema no ha vuelto a
aparecer de forma sostenida, no solo tras una única observación
puntual positiva. Estas dos cosas pueden requerir tiempos distintos
según el tipo de acción — razónalo específicamente para este caso.
Después, compara explícitamente esos tiempos estimados contra el
número real de ciclos transcurridos ({cycles_since_approval}).
- Si NO ha pasado tiempo suficiente para (a) → Decisión final:
  CONTINUAR, indicando aproximadamente cuánto tiempo más falta. No
  sigas más.
- Si (a) se cumple pero NO (b) → Decisión final: CONTINUAR,
  indicando explícitamente que la señal inicial es prometedora pero
  aún falta confirmar que se sostiene en el tiempo antes de cerrar.
  No sigas más.
- Si ambas se cumplen → continúa al Paso 3.

PASO 3 (dado que Paso 1 y 2 se cumplieron): Define el criterio de
éxito específico para ESTE patrón, antes de mirar ninguna evidencia
de EFECTIVIDAD todavía (esto es distinto de la evidencia de
ejecución ya evaluada en el Paso 1). Razona: dado lo que se aprobó
hacer, ¿qué evidencia concreta demostraría realmente que el problema
original mejoró? No apliques una regla genérica idéntica para todos
los casos — el criterio correcto depende del tipo de acción. El
criterio debe ser REALISTA y proporcional: una mejora clara y
sostenida (por ejemplo, "las quejas bajan claramente"), nunca una
perfección absoluta ("cero quejas", "ausencia total"). Indica este
criterio en una frase clara.

PASO 4: Reúne TODA la evidencia externa disponible sobre si el
problema mejoró — reseñas relevantes, valoración media, Y
confirmación humana directa sobre el RESULTADO específicamente (no
sobre si se ejecutó, eso ya quedó resuelto en el Paso 1). Descarta
explícitamente cualquier reseña que no mencione directa y
específicamente este patrón.

PASO 5: Compara la evidencia reunida en el Paso 4 contra el criterio
que definiste en el Paso 3. Decide:
- Cumple con evidencia sólida (2+ señales coincidiendo, o 1 señal
  fuerte + confirmación humana directa y específica sobre el
  resultado) → CERRAR
- Una sola señal positiva débil, sin refuerzo → CONTINUAR (explica
  por qué es aún una señal temprana, no confirmada)
- MEJORA PARCIAL: la mayoría de la evidencia muestra mejora, pero queda
  un problema residual o puntual (por ejemplo, un comentario aislado
  sobre un detalle) → CONTINUAR, proponiendo un AJUSTE concreto y
  pequeño dentro del mismo plan. Un comentario aislado no pesa lo
  mismo que varias señales coincidentes: no lo trates como una
  contradicción.
- Contradicción REAL: señales de peso parecido que apuntan en
  direcciones opuestas sobre el problema principal (por ejemplo, el
  personal dice que mejoró pero varios socios dicen que sigue igual
  o peor) → PIVOTAR, explicando la contradicción específica.
- Ninguna señal externa relevante de mejora, o empeoramiento → PIVOTAR
Reserva PIVOTAR para cuando el enfoque en sí no funciona, no para
cuando funciona pero necesita un retoque.

---

Formato de tu respuesta:

🔁 CONTINUIDAD — [patrón] (ciclo {cycles_since_approval})

Paso 1: [nivel de evidencia de ejecución evaluado]
Paso 2: [razonamiento sobre el tiempo — primer efecto Y sostenibilidad — comparado contra el ciclo real]
Paso 3: [criterio de éxito definido, antes de ver evidencia de resultado]
Paso 4: [evidencia de efectividad reunida]
Paso 5: [comparación contra el criterio y decisión]

Decisión: [🚩 FLAG DE IMPLEMENTACIÓN / 🔵 CONTINUAR / 🟢 CERRAR / 🟠 PIVOTAR]

Negritas: en cada paso, pon en **negrita** solo la conclusión clave de
ese paso (3-6 palabras); en el párrafo final, pon en negrita la razón
principal. Como máximo una negrita por paso, y nunca una frase completa.
No pongas en negrita la línea "Decisión:".

Si la decisión es CERRAR, añade un párrafo breve en lenguaje claro y
natural — como si se lo contaras directamente al propietario —
contando la historia completa: cuál era el problema original, qué se
intentó, y por qué la evidencia sostenida en el tiempo demuestra que
funcionó.

Si la decisión es CONTINUAR por MEJORA PARCIAL, añade un párrafo
breve con el ajuste concreto que recomiendas mantener o probar hasta
el siguiente seguimiento.

Si la decisión es PIVOTAR, añade un párrafo igual de claro,
explicando qué se intentó, por qué no fue suficiente según la
evidencia real, y una hipótesis concreta de qué probar diferente la
próxima vez.

Ahora razona y decide el caso real indicado."""


def run_outcome_check_agent(pattern_name: str, verification_method: str, verification_result: str,
                              action_description: str, cycles_since_approval: int,
                              new_reviews_since_approval: str = "Ninguna",
                              rating_before: str = "No disponible", rating_after: str = "No disponible"):
    prompt = build_prompt(pattern_name, verification_method, verification_result,
                           action_description, cycles_since_approval,
                           new_reviews_since_approval, rating_before, rating_after,
                           club_profile=load_club_profile())
    response = client.models.generate_content(model="gemini-3.7-flash", contents=prompt)
    return response.text


def run_outcome_check_from_db(pattern_name: str,
                                new_reviews_since_approval: str = "Ninguna",
                                rating_before: str = "No disponible",
                                rating_after: str = "No disponible"):
    """Real-use version: pulls the pattern's stored data from
    Supabase automatically."""
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


def run_outcome_check_for(pattern_data: dict,
                          new_reviews_since_approval: str = "Ninguna",
                          rating_before: str = "No disponible",
                          rating_after: str = "No disponible"):
    """Same check, but using the pattern row the caller already has
    (read by id), so it never depends on matching the pattern's name."""
    return run_outcome_check_agent(
        pattern_name=pattern_data["pattern_name"],
        verification_method=pattern_data.get("verification_method") or "No disponible",
        verification_result=pattern_data.get("verification_result") or "No confirmado todavía",
        action_description=pattern_data.get("approved_action") or "",
        cycles_since_approval=pattern_data.get("cycles_since_approval") or 0,
        new_reviews_since_approval=new_reviews_since_approval,
        rating_before=rating_before,
        rating_after=rating_after,
    )


if __name__ == "__main__":
    print("=== PRUEBA REAL: leyendo desde Supabase ===\n")
    result = run_outcome_check_from_db(
        "Exceso de arena en las pistas",
        new_reviews_since_approval="""Socio-Z: "Las pistas ya no tienen tanta arena, se nota la mejora.\"""",
        rating_before="4.2", rating_after="4.4"
    )
    print(result)