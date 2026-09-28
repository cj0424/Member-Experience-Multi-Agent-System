"""
streamlit_app.py — entry point. Run with:
    python -m streamlit run streamlit_app.py

1. Defines the navigation, so the sidebar follows the owner's journey:
   Resumen → 1 · Detectar → 2 · Preparar → 3 · Seguir → 4 · Historial.
   Each page lives in its own file, with its own design:
   - home.py                      → Resumen (dashboard)
   - pages/2_Nuevos_Patrones.py   → 1 · Detectar
   - pages/3_Kits_de_Ejecucion.py → 2 · Preparar
   - pages/4_Seguimiento.py       → 3 · Seguir
   - pages/5_Historial.py         → 4 · Historial
2. Adds the floating "💬 Ayuda" button, once, so it appears on every page.
   It opens a chat with Pala, the club's assistant (agents/faq_agent.py), which reads all
   the club's patterns at once and answers in a few lines: what to do now
   (page → card → button, and why), how the club is doing, what to prepare
   for the next check-ins, tasks for the Monday meeting, rejected ideas, or
   a short story of one pattern. Under each answer, buttons take the owner
   straight to the pages it mentions. It never changes any data.
"""

import os
import sys

import streamlit as st

sys.path.append(os.path.join(os.path.dirname(__file__), "agents"))

SUGGESTIONS = [
    "🧭 ¿Qué hago ahora?",
    "📊 ¿Cómo va el club?",
    "🔁 ¿Qué necesito para los próximos seguimientos?",
    "📅 Tareas para la reunión del lunes",
    "🚫 ¿Qué ideas ya hemos descartado?",
]

# Pages the assistant can send the owner to, as named in its answers.
PAGE_LINKS = [
    ("1 · Detectar", "pages/2_Nuevos_Patrones.py", "🔍"),
    ("2 · Preparar", "pages/3_Kits_de_Ejecucion.py", "📋"),
    ("3 · Seguir", "pages/4_Seguimiento.py", "🔁"),
    ("4 · Historial", "pages/5_Historial.py", "📈"),
]


def render_page_buttons(answer: str, key: str):
    """'Ir a …' buttons for the pages the answer mentions, in the order
    they appear, so the owner goes straight there."""
    found = sorted(
        ((answer.find(name), name, path, icon) for name, path, icon in PAGE_LINKS if name in answer),
        key=lambda x: x[0],
    )
    if not found:
        return
    cols = st.columns(len(found))
    for col, (_, name, path, icon) in zip(cols, found):
        if col.button(f"{icon} Ir a {name}", key=f"{key}_{name}", type="primary", width="stretch"):
            st.switch_page(path)

# Floating help button (bottom-right, above everything) + chat styling.
st.markdown("""
<style>
.st-key-faq_fab {
    position: fixed;
    bottom: 26px;
    right: 30px;
    z-index: 999;
    width: auto !important;
}
div.st-key-faq_fab button[kind="secondary"] {
    background-color: #C2410C !important;
    border: 1px solid #C2410C !important;
    color: #FFFFFF !important;
    font-size: 17px !important;
    font-weight: 700 !important;
    border-radius: 999px !important;
    padding: 10px 22px !important;
    box-shadow: 0 8px 22px rgba(194,65,12,0.30) !important;
}
div.st-key-faq_fab button[kind="secondary"]:hover { background-color: #9A3412 !important; }
div.st-key-faq_fab button[kind="secondary"] p { color: #FFFFFF !important; }

div[role="dialog"] [data-testid="stChatMessage"] p {
    font-size: 16px !important;
    line-height: 1.65 !important;
}
.faq-hint { font-size: 15px; color: #748092; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)


@st.dialog("💬 Pala · tu asistente del club", width="large")
def faq_dialog():
    messages = st.session_state.setdefault("faq_messages", [])

    if not messages:
        st.markdown('<div class="faq-hint">Hola, soy Pala. Pregúntame lo que quieras sobre tus patrones: '
                    'qué hacer ahora, cómo van, qué les falta o qué pasó con uno concreto. '
                    'No cambio nada en la app, solo te oriento.</div>', unsafe_allow_html=True)
        for i, suggestion in enumerate(SUGGESTIONS):
            if st.button(suggestion, key=f"faq_sug_{i}", type="secondary", width="stretch"):
                st.session_state["faq_pending"] = suggestion

    # Messages go in a box drawn above the input; the input is read first,
    # so we know whether a new answer is coming (then only the newest
    # answer shows its "Ir a …" buttons).
    chat_box = st.container()
    typed = st.chat_input("Escribe tu pregunta, por ejemplo: ¿qué pasó con el aparcamiento?", key="faq_input")
    question = typed or st.session_state.pop("faq_pending", None)

    with chat_box:
        for i, m in enumerate(messages):
            with st.chat_message(m["role"], avatar="🎾" if m["role"] == "assistant" else "🙂"):
                st.markdown(m["content"])
                if m["role"] == "assistant" and i == len(messages) - 1 and not question:
                    render_page_buttons(m["content"], key=f"faq_go_{i}")

        if question:
            with st.chat_message("user", avatar="🙂"):
                st.markdown(question)
            with st.chat_message("assistant", avatar="🎾"):
                with st.spinner("Revisando tus patrones..."):
                    try:
                        from faq_agent import run_faq_agent
                        answer = run_faq_agent(question, messages)
                    except Exception:
                        answer = ("Ahora mismo no puedo responder. Comprueba la conexión "
                                  "e inténtalo de nuevo en un momento.")
                st.markdown(answer)
                render_page_buttons(answer, key=f"faq_go_{len(messages) + 1}")
            messages.append({"role": "user", "content": question})
            messages.append({"role": "assistant", "content": answer})

    if messages:
        with st.expander("Más preguntas rápidas"):
            for i, suggestion in enumerate(SUGGESTIONS):
                if st.button(suggestion, key=f"faq_more_{i}", type="secondary", width="stretch"):
                    st.session_state["faq_pending"] = suggestion
                    try:
                        st.rerun(scope="fragment")
                    except Exception:
                        st.rerun()

    if messages and st.button("🧹 Empezar de nuevo", key="faq_reset", type="secondary"):
        messages.clear()
        try:
            st.rerun(scope="fragment")   # redraws only the chat, keeps it open
        except Exception:
            st.rerun()


# Drawn before the page, so it's there even if a page stops early.
with st.container(key="faq_fab"):
    if st.button("💬 Ayuda", key="faq_open"):
        faq_dialog()

navigation = st.navigation([
    st.Page("home.py", title="Resumen", icon="🏠", default=True),
    st.Page("pages/2_Nuevos_Patrones.py", title="1 · Detectar", icon="🔍"),
    st.Page("pages/3_Kits_de_Ejecucion.py", title="2 · Preparar", icon="📋"),
    st.Page("pages/4_Seguimiento.py", title="3 · Seguir", icon="🔁"),
    st.Page("pages/5_Historial.py", title="4 · Historial", icon="📈"),
])
navigation.run()