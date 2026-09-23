"""
Insights Agent — reads all reviews AND post-visit survey
responses, finds real, recurring patterns, distinguishes them
from one-off noise, tags patterns as still active vs. already
resolved, and treats Google Reviews and the post-visit QR survey
as genuinely independent sources, applying stronger confidence
when a pattern is corroborated across BOTH, since different
collection methods carry different biases.
"""

import os
from dotenv import load_dotenv
from google import genai
from evidence_layer import load_reviews

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def build_prompt(reviews: list[dict], survey_responses: list[dict]) -> str:
    """Combines both sources into one prompt, each clearly labeled
    so Gemini can reason about them as genuinely distinct sources,
    not one merged pool."""
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
7. Termina con una nota de limitación sobre estas dos fuentes.

Sigue EXACTAMENTE este formato para cada patrón confirmado:

🔍 PATRÓN — [nombre del patrón]
[🟢 ACTIVO / 📁 HISTÓRICO — YA RESUELTO]
📎 Evidencia: [número] menciones ([lista de IDs]) — [fuente(s): reseñas / encuesta / ambas]
🟢/🟡/🔴 Confianza: [Alto/Moderado/Bajo]
🧭 Qué significa: [interpretación breve, 1-2 frases]

Ejemplo de un patrón bien formado, con evidencia cruzada:

🔍 PATRÓN — Exceso de arena en las pistas
🟢 ACTIVO
📎 Evidencia: 4 reseñas (REV-004, REV-008) + 3 respuestas de encuesta (ENC-002, ENC-008, ENC-017) — fuentes: reseñas Y encuesta
🟢 Confianza: Alto
🧭 Qué significa: el problema está confirmado de forma independiente por dos fuentes distintas, lo que descarta que sea solo una percepción de quienes escriben reseñas públicas.

Ahora aplica este mismo formato a los patrones reales que encuentres."""


def run_insights_agent(
    review_filepath: str = "data/reviews/padel_club_reviews_anonymized.txt",
    survey_filepath: str = "data/reviews/padel_club_survey_sept_week3.txt"
):
    reviews = load_reviews(review_filepath)
    survey_responses = load_reviews(survey_filepath)
    prompt = build_prompt(reviews, survey_responses)

    response = client.models.generate_content(
        model="gemini-3.7-flash",
        contents=prompt
    )
    return response.text


if __name__ == "__main__":
    result = run_insights_agent()
    print(result)