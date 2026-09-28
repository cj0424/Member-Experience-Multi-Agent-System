"""
Insights Agent — reads all reviews AND post-visit survey
responses, finds real, recurring patterns, distinguishes them
from one-off noise, tags patterns as still active vs. already
resolved, and treats Google Reviews and the post-visit QR survey
as genuinely independent sources, applying stronger confidence
when a pattern is corroborated across BOTH, since different
collection methods carry different biases.

Memory: Gemini doesn't remember earlier runs, so the graph passes
in every pattern already registered in Supabase (known_patterns).
The agent then marks each confirmed pattern as NUEVO, YA
REGISTRADO or REAPARECE, instead of rediscovering the same
problem under a new name.
"""

import os
from dotenv import load_dotenv
from google import genai
from evidence_layer import load_reviews

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def build_prompt(reviews: list[dict], survey_responses: list[dict],
                 known_patterns: str = "Ninguno todavía.") -> str:
    """Combines both sources into one prompt, each clearly labeled
    so Gemini can reason about them as genuinely distinct sources,
    not one merged pool — plus the patterns the system already
    knows about."""
    review_block = "\n\n".join(
        f"[{r['id']}] {r['header']}\n{r['text']}" for r in reviews
    )
    survey_block = "\n\n".join(
        f"[{s['id']}] {s['header']}\n{s['text']}" for s in survey_responses
    )

    return f"""Eres un analista revisando la experiencia de socios de un club de
pádel en Madrid, usando DOS fuentes de evidencia independientes.

FUENTE 1 — RESEÑAS PÚBLICAS DE GOOGLE:
{review_block}

FUENTE 2 — RESPUESTAS A ENCUESTA POST-SESIÓN (vía QR code):
{survey_block}

PATRONES YA REGISTRADOS EN EL SISTEMA (de análisis anteriores):
{known_patterns}

Tu tarea:
1. Clasifica cada mención relevante en una categoría (por ejemplo: arena/
   césped, temperatura, reservas, superficie de pista, limpieza, personal).
2. Dentro de cada categoría, identifica patrones REALES que se repiten en
   al menos 3 reseñas/respuestas independientes EN TOTAL. No inventes
   patrones a partir de una sola mención — indícalas por separado como
   "no suficiente evidencia".
3. Si hay evidencia contradictoria sobre el mismo tema, menciónalo
   explícitamente.
4. Para cada patrón confirmado, evalúa si la propia evidencia muestra
   que el problema ya se resolvió o si sigue activo. Etiqueta cada
   patrón confirmado como:
   - 🟢 ACTIVO (necesita acción) — si no hay evidencia de que ya se
     resolvió.
   - 📁 HISTÓRICO — YA RESUELTO (no requiere acción) — si la propia
     evidencia muestra un antes/después con una mejora clara y
     sostenida.
5. TRIANGULACIÓN — para cada patrón confirmado, identifica en qué
   fuente(s) aparece. Trata las reseñas y la encuesta como fuentes
   genuinamente distintas, con sesgos distintos: las reseñas solo
   atraen opiniones muy fuertes (positivas o negativas) y llegan con
   poca frecuencia; la encuesta capta opiniones más moderadas y llega
   con más frecuencia, pero solo de quien tuvo un momento libre para
   responder. Evalúa:
   - Si el patrón tiene evidencia genuinamente repetida (no una
     mención aislada) DENTRO DE CADA fuente por separado — considerando
     que ambas fuentes se acumulan a ritmos distintos, no exijas el
     mismo número exacto en ambas — la confianza debe ser 🟢 Alta,
     ya que dos métodos de recolección con sesgos diferentes están
     coincidiendo de forma independiente.
   - Si el patrón tiene 3+ menciones en total pero está concentrado
     en UNA sola fuente: confianza 🟡 Moderada como máximo — el sesgo
     propio de esa fuente no ha sido descartado por una segunda
     fuente independiente.
   Indica explícitamente en cada patrón qué fuente(s) lo respaldan
   (ej. "confirmado por reseñas Y encuesta" vs. "confirmado solo por
   reseñas").
6. En la sección de evidencia insuficiente, lista cada mención de
   forma INDIVIDUAL y separada — nunca agrupes menciones distintas
   bajo una sola etiqueta, aunque parezcan relacionadas. Cada
   mención aislada merece su propia línea, citando su ID específico
   y su fuente.
7. REGISTRO — compara cada patrón confirmado con la lista de patrones
   ya registrados. Es el MISMO patrón si trata del mismo problema o
   la misma fortaleza, aunque las palabras sean distintas (ej. "bar
   renovado" y "valoración de la cafetería tras la reforma" son el
   mismo). Marca cada patrón con:
   - NUEVO — si no se parece a ninguno de la lista.
   - YA REGISTRADO — #id — si coincide con uno de la lista. Usa
     entonces EXACTAMENTE el nombre registrado, no uno nuevo.
   - REAPARECE — #id — solo si coincide con uno CERRADO y la
     evidencia muestra que vuelve a estar activo.
   Si un patrón nuevo junta varios temas, y uno de ellos ya está
   registrado, sepáralo: no mezcles un tema registrado dentro de un
   patrón nuevo.
8. Termina con una nota de limitación sobre estas dos fuentes.

Sigue EXACTAMENTE este formato para cada patrón confirmado:

🔍 PATRÓN — [nombre del patrón]
[🟢 ACTIVO / 📁 HISTÓRICO — YA RESUELTO]
🔗 Registro: [NUEVO / YA REGISTRADO — #id / REAPARECE — #id]
📎 Evidencia: [número] menciones ([lista de IDs]) — [fuente(s): reseñas / encuesta / ambas]
🟢/🟡/🔴 Confianza: [Alto/Moderado/Bajo]
🧭 Qué significa: [interpretación breve, 1-2 frases]

Ejemplo de un patrón bien formado, con evidencia cruzada:

🔍 PATRÓN — Exceso de arena en las pistas
🟢 ACTIVO
🔗 Registro: NUEVO
📎 Evidencia: 4 reseñas (REV-004, REV-008) + 3 respuestas de encuesta (ENC-002, ENC-008, ENC-017) — fuentes: reseñas Y encuesta
🟢 Confianza: Alto
🧭 Qué significa: el problema está confirmado de forma independiente por dos fuentes distintas, lo que descarta que sea solo una percepción de quienes escriben reseñas públicas.

Ahora aplica este mismo formato a los patrones reales que encuentres."""


def run_insights_agent(
    review_filepath: str = "data/reviews/padel_club_reviews_anonymized.txt",
    survey_filepath: str = "data/reviews/padel_club_survey_sept_week3.txt",
    known_patterns: str = "Ninguno todavía."
):
    reviews = load_reviews(review_filepath)
    survey_responses = load_reviews(survey_filepath, prefix="ENC")
    prompt = build_prompt(reviews, survey_responses, known_patterns)

    response = client.models.generate_content(
        model="gemini-3.7-flash",
        contents=prompt
    )
    return response.text


if __name__ == "__main__":
    result = run_insights_agent()
    print(result)