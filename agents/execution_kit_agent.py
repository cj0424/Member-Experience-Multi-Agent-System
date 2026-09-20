"""
Execution Kit Agent — takes ONE approved recommendation (already
containing specific actions, from Action Planning Agent) and
reasons freely about what it actually needs to become real: text
to communicate something, a procurement list, direct outreach to
specific people, or anything else the recommendation genuinely
calls for. No fixed menu of output types — fully open-ended, so
it works on any future pattern, not just the ones already tested.

LIMITATIONS (by design):
- Drafts text and lists only. Never sends, posts, purchases, or
  implements anything.
- Cannot know real budget, staffing, or calendar.
- Cannot make the decision — that already happened in Action
  Planning's approval step.
- Cannot verify anything got done — that's Follow-Through's job.
"""

import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def build_prompt(approved_recommendation: str) -> str:
    """Derives an execution kit by reasoning about what THIS
    specific recommendation needs — no example output types given,
    fully open-ended."""
    return f"""Eres un asistente que ayuda al propietario de un club de pádel
a convertir una recomendación YA APROBADA en piezas reales y listas
para usar.

RECOMENDACIÓN APROBADA:
{approved_recommendation}

Antes de redactar nada, analiza la recomendación y pregúntate:
- ¿Hay algo que comunicar a alguien (personal, socios, un
  proveedor)? Si es así, redacta el texto exacto.
- ¿Hay algo físico que adquirir o preparar? Si es así, indícalo
  con claridad.
- ¿Hay algo que requiere contactar directamente a personas
  específicas (por ejemplo, socios concretos que se quejaron)? Si
  es así, redacta ese contacto.
- ¿Hay cualquier otra pieza concreta — sin importar su tipo — que
  alguien necesitaría literalmente en la mano para ejecutar esto?

No existe una lista fija de tipos de material — decide tú, caso
por caso, qué necesita ESTA recomendación específica. Una
recomendación puede necesitar una sola pieza, varias, o incluso un
tipo de material que no se haya mencionado aquí. Usa tu propio
criterio por completo.

Reglas:
- NO inventes acciones nuevas — trabaja solo con lo ya aprobado.
- Cada pieza debe estar lista para usar tal cual, con un título
  que tú mismo definas según lo que realmente sea.
- Tu única función es REDACTAR. Nunca envíes, publiques, compres
  ni implementes nada.

Formato:

📄 KIT DE EJECUCIÓN

[Una pieza por cada necesidad real identificada]

📋 Ejecución:
Responsable: [rol]
Plazo sugerido: [plazo]
Cómo verificar: [método]

Ahora razona desde cero y redacta el kit de ejecución real para la
recomendación aprobada indicada."""


def run_execution_kit_agent(approved_recommendation: str):
    prompt = build_prompt(approved_recommendation)

    response = client.models.generate_content(
        model="gemini-3.7-flash",
        contents=prompt
    )
    return response.text


if __name__ == "__main__":
    # Realistic: only ONE option was approved, not both — matching
    # what Execution Kit Agent will actually receive once connected
    # via LangGraph. This is Option 1 from the REVISED (low-cost)
    # recommendation, after the owner rejected the first, expensive one.
    test_approved_recommendation = """Opción aprobada: Protocolo de ventilación natural y ajuste comercial
Gestión de portones: en verano, abrir ventilación cruzada a
primera hora de la mañana y noche, cerrando en horas punta de
calor; en invierno, sellar rendijas críticas con burletes
autoadhesivos o faldones de goma económicos.
Incentivos horarios: lanzar promociones o tarifas reducidas en
las horas de temperatura más extrema."""

    result = run_execution_kit_agent(test_approved_recommendation)
    print(result)