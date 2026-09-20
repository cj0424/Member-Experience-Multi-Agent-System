"""
Insights Agent — reads all reviews and asks Gemini to find real,
recurring patterns, distinguishing them from one-off noise.
"""

import os
from dotenv import load_dotenv
from google import genai
from evidence_layer import load_reviews

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def build_prompt(reviews: list[dict]) -> str:
    """Combines all reviews into one prompt for Gemini to analyze."""
    review_block = "\n\n".join(
        f"[{r['id']}] {r['header']}\n{r['text']}" for r in reviews
    )

    return f"""Eres un analista revisando reseñas reales de un club de pádel en Madrid.

Aquí están todas las reseñas disponibles, cada una con su ID y fecha:

{review_block}

Tu tarea:
1. Clasifica cada mención relevante en una categoría (por ejemplo: arena/
   césped, temperatura, reservas, superficie de pista, limpieza, personal).
2. Dentro de cada categoría, identifica patrones REALES que se repiten en
   al menos 3 reseñas independientes. No inventes patrones a partir de
   una sola mención — indícalas por separado como "no suficiente evidencia".
3. Si hay evidencia contradictoria sobre el mismo tema, menciónalo
   explícitamente.
4. En la sección de evidencia insuficiente, lista cada mención de
   forma INDIVIDUAL y separada — nunca agrupes menciones distintas
   bajo una sola etiqueta, aunque parezcan relacionadas. Cada
   mención aislada merece su propia línea, citando su ID específico.
5. Termina con una nota de limitación sobre estas reseñas públicas.

Sigue EXACTAMENTE este formato para cada patrón confirmado:

🔍 PATRÓN — [nombre del patrón]
📎 Evidencia: [número] reseñas ([lista de IDs])
🟢/🟡/🔴 Confianza: [Alto/Moderado/Bajo]
🧭 Qué significa: [interpretación breve, 1-2 frases]

Ejemplo de un patrón bien formado:

🔍 PATRÓN — Exceso de arena en las pistas
📎 Evidencia: 4 reseñas (REV-004, REV-008, REV-012, REV-025)
🟢 Confianza: Alto
🧭 Qué significa: la frecuencia actual de redistribución de arena
puede no ser suficiente para el nivel de uso del club.

Ahora aplica este mismo formato a los patrones reales que encuentres."""


def run_insights_agent():
    reviews = load_reviews("data/reviews/mcp_padel_reviews.txt")
    prompt = build_prompt(reviews)

    response = client.models.generate_content(
        model="gemini-3.7-flash",
        contents=prompt
    )
    return response.text


if __name__ == "__main__":
    result = run_insights_agent()
    print(result)