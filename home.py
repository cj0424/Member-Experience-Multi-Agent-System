"""
home.py — Resumen (Dashboard Home). Opened by streamlit_app.py, which
now only sets up the navigation.

Club de Pádel — Dashboard de mejora continua

Visual theme:

Primary: Deep Navy #030338
Secondary: Navy #1E3F59
Accent: Lime #ACD803
Soft Lime: #EFF5D1
Positive: Deep Green #274A22
Neutral: #252445
Border: #DBDFE3
Page Background: #F8FAF7

Header font: Paytone One
"""

import streamlit as st
import sys
import os
import html
import re
import plotly.graph_objects as go

sys.path.append(os.path.join(os.path.dirname(__file__), "agents"))

from outcome_check_agent import supabase
import db
from auth import require_login, can, actor_label

st.set_page_config(
    page_title="Dashboard — Club de Pádel",
    layout="wide"
)
role = require_login("ver")

st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Paytone+One&display=swap" rel="stylesheet">

<style>

.stApp {
    background-color: #F8FAF7;
}

.block-container {
    padding-top: 2.2rem;
    padding-bottom: 3rem;
}

h1,
h2,
h3,
[data-testid="stSubheader"] {
    font-family: 'Paytone One', sans-serif !important;
    color: #030338 !important;
    letter-spacing: -0.3px;
}

h1 {
    font-size: 2.6rem !important;
    line-height: 1.15 !important;
}

h2 {
    font-size: 1.8rem !important;
}

h3 {
    font-size: 1.35rem !important;
}

.dashboard-subtitle {
    color: #748092;
    font-size: 0.95rem;
}

[data-testid="stMetric"] {
    background-color: #FFFFFF;
    border: 1px solid #DBDFE3;
    border-radius: 12px;
    padding: 17px 20px;
    box-shadow: none;
}

[data-testid="stMetricLabel"] {
    color: #252445 !important;
    font-size: 0.86rem !important;
    font-weight: 600 !important;
}

[data-testid="stMetricValue"] {
    color: #030338 !important;
    font-family: 'Paytone One', sans-serif !important;
    font-size: 2.25rem !important;
    line-height: 1.1 !important;
}

[data-testid="stMetricDelta"] {
    display: none;
}

div[data-testid="column"]:nth-of-type(1) [data-testid="stMetric"] {
    border-top: 3px solid #ACD803;
}

div[data-testid="column"]:nth-of-type(2) [data-testid="stMetric"] {
    border-top: 3px solid #274A22;
}

div[data-testid="column"]:nth-of-type(3) [data-testid="stMetric"] {
    border-top: 3px solid #1E3F59;
}

div[data-testid="column"]:nth-of-type(4) [data-testid="stMetric"] {
    border-top: 3px solid #C2410C;
}

hr {
    border: none;
    border-top: 1px solid #DBDFE3;
}

/* Pattern cards — quiet by default, orange only for the one being read */
div[class*="st-key-pattern_card_"],
div[class*="st-key-pattern_open_"] {
    background-color: #FFFFFF !important;
    border-radius: 16px !important;
    padding: 20px 28px !important;
    margin-bottom: 6px;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

div[class*="st-key-pattern_card_"] {
    border: 1px solid #DBDFE3 !important;
    box-shadow: none !important;
}

div[class*="st-key-pattern_card_"]:hover {
    border-color: #F2B08F !important;
    box-shadow: 0 4px 14px rgba(194,65,12,0.08) !important;
}

div[class*="st-key-pattern_open_"] {
    border: 2px solid #C2410C !important;
    box-shadow: 0 8px 24px rgba(194,65,12,0.12) !important;
}

.pattern-name {
    color: #030338;
    font-size: 20px;
    font-weight: 700;
    line-height: 1.35;
}

div[class*="st-key-pattern_open_"] .pattern-name {
    font-size: 23px;
}

.tag {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 5px 12px;
    border-radius: 999px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.45px;
    line-height: 1;
    white-space: nowrap;
}

.tag-cerrar {
    background-color: #15803d;
    color: #FFFFFF;
}

.tag-continuar {
    background-color: #2563eb;
    color: #FFFFFF;
}

.tag-pivotar {
    background-color: #ea580c;
    color: #FFFFFF;
}

.tag-flag {
    background-color: #dc2626;
    color: #FFFFFF;
}

.tag-kit {
    background-color: #FEF3C7;
    color: #92400E;
}

.tag-default {
    background-color: #DBDFE3;
    color: #252445;
}

button[kind="primary"] {
    background-color: #1E3F59 !important;
    border: 1px solid #1E3F59 !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
    border-radius: 8px !important;
}

button[kind="primary"]:hover {
    background-color: #030338 !important;
    border-color: #030338 !important;
}

button[kind="secondary"] {
    background-color: #FFFFFF !important;
    border: 1px solid #1E3F59 !important;
    color: #1E3F59 !important;
    font-weight: 700 !important;
    border-radius: 8px !important;
}

button[kind="secondary"]:hover {
    background-color: #EFF5D1 !important;
    border-color: #ACD803 !important;
    color: #030338 !important;
}

.summary-box {
    background-color: #EFF5D1;
    border-left: 4px solid #ACD803;
    border-radius: 8px;
    padding: 16px 20px;
    font-size: 16px;
    line-height: 1.7;
    color: #030338;
    margin: 12px 0;
}

strong.hl {
    background: linear-gradient(transparent 55%, #DCEF8F 55%);
    padding: 0 2px;
    color: #030338;
}

.status-note {
    background: #F1F5F9;
    border-left: 4px solid #1E3F59;
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 15px;
    color: #1E3F59;
    margin: 8px 0;
}
.status-escalated {
    background: #FEF2F2;
    border-left-color: #dc2626;
    color: #7f1d1d;
}

.js-plotly-plot {
    margin-top: 2px;
    margin-bottom: 2px;
}

.stCaption {
    color: #748092 !important;
}

/* ---------- Journey bar (clickable, shows what's waiting) ---------- */

.st-key-journey { gap: 8px !important; margin: 2px 0 8px 0; }
div[class*="st-key-jr_"] [data-testid="stPageLink"] a {
    padding: 5px 14px !important;
    border-radius: 999px !important;
    background: #FFFFFF !important;
    border: 1px solid #DBDFE3 !important;
    text-decoration: none !important;
}
div[class*="st-key-jr_"] [data-testid="stPageLink"] a * {
    font-size: 14px !important;
    font-weight: 700 !important;
    color: #748092 !important;
}
div[class*="st-key-jr_step"] [data-testid="stPageLink"] a:hover {
    border-color: #F2B08F !important;
    background: #FFF7ED !important;
}
div[class*="st-key-jr_active"] [data-testid="stPageLink"] a {
    background: #C2410C !important;
    border-color: #C2410C !important;
}
div[class*="st-key-jr_active"] [data-testid="stPageLink"] a * { color: #FFFFFF !important; }

.agent-line {
    font-size: 14px;
    font-weight: 600;
    color: #1E3F59;
    margin: -2px 0 6px 0;
}

/* ---------- Pattern lifecycle stepper ---------- */

.stepper { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 6px 0 14px 0; }
.stp {
    font-size: 13px;
    font-weight: 700;
    padding: 4px 12px;
    border-radius: 999px;
    border: 1px solid #DBDFE3;
    background: #FFFFFF;
    color: #94a3b8;
}
.stp-done { background: #EFF5D1; border-color: #ACD803; color: #274A22; }
.stp-now  { background: #C2410C; border-color: #C2410C; color: #FFFFFF; }
.stp-arrow { color: #DBDFE3; font-size: 13px; }
.stp-off  { background: #F1F5F9; border-color: #94a3b8; color: #475569; }
.stp-alert { background: #FEF2F2; border-color: #dc2626; color: #7f1d1d; }

.tag-kit { background-color: #FEF3C7; color: #92400E; border: 1px solid #F59E0B; }
.tag-seg { background-color: #E0E7FF; color: #1E3F59; }
.tag-closed { background-color: #15803d; color: #FFFFFF; }
.tag-esc { background-color: #7f1d1d; color: #FFFFFF; }
.tag-disc { background-color: #94a3b8; color: #FFFFFF; }

/* ---------- "Tu siguiente paso" ---------- */

div[class*="st-key-next_"] {
    background: #FFFFFF !important;
    border: 1px solid #DBDFE3 !important;
    border-radius: 14px !important;
    padding: 16px 18px !important;
    height: 100%;
}
div[class*="st-key-next_hot_"] {
    border: 2px solid #C2410C !important;
    box-shadow: 0 6px 18px rgba(194,65,12,0.10) !important;
}
.next-title { font-size: 15px; font-weight: 800; color: #030338; }
.next-text { font-size: 15px; color: #1e293b; margin: 6px 0 10px 0; min-height: 44px; }
.next-count { font-family: 'Paytone One', sans-serif; font-size: 2rem; color: #030338; line-height: 1; }

</style>
""", unsafe_allow_html=True)


TAG_MAP = {
    "CERRAR": ("CERRAR", "tag-cerrar", "#15803d"),
    "CONTINUAR": ("CONTINUAR", "tag-continuar", "#2563eb"),
    "PIVOTAR": ("PIVOTAR", "tag-pivotar", "#ea580c"),
    "FLAG": ("FLAG", "tag-flag", "#dc2626"),
}


# ---------------------------------------------------------------------------
# Journey helpers (same on every page): clickable journey bar, next-step
# buttons, links to a pattern's history, lifecycle stepper, status tags
# ---------------------------------------------------------------------------

JOURNEY = [
    (1, "Detectar", "pages/2_Nuevos_Patrones.py"),
    (2, "Preparar", "pages/3_Kits_de_Ejecucion.py"),
    (3, "Seguir", "pages/4_Seguimiento.py"),
    (4, "Historial", "pages/5_Historial.py"),
]
PAGE_PATHS = {name: path for _, name, path in JOURNEY}


def render_journey(active: int):
    """The four steps as links, each showing what's waiting there."""
    try:
        counts = db.get_journey_counts()
    except Exception:
        counts = {}
    badges = {2: counts.get("pending_kit"), 3: counts.get("due_checkins"), 4: counts.get("escalated")}
    with st.container(horizontal=True, key="journey"):
        for n, name, path in JOURNEY:
            badge = badges.get(n)
            label = f"{n} · {name}" + (f"  ({badge})" if badge else "")
            with st.container(key=f"jr_{'active' if n == active else 'step'}_{n}", width="content"):
                try:
                    st.page_link(path, label=label)
                except Exception:
                    st.markdown(f"**{label}**")


def go_to_page(path: str):
    try:
        st.switch_page(path)
    except Exception:
        st.info("Abre la página en el menú lateral.")


def next_step_button(label: str, path: str, key: str):
    if st.button(label, key=key, type="primary"):
        go_to_page(path)


def history_button(pattern_id: int, key: str):
    if st.button("📈 Historia", key=key, type="secondary"):
        st.session_state["hist_pattern"] = pattern_id
        go_to_page("pages/5_Historial.py")


def stage_tag(p: dict, checkins: int) -> str:
    """One vocabulary for a pattern's status, used on every page."""
    stage = db.pattern_stage(p, checkins)
    if stage == "Plan":
        return '<span class="tag tag-kit">PENDIENTE DE KIT</span>'
    if stage == "Kit":
        return '<span class="tag tag-seg">EN SEGUIMIENTO</span>'
    if stage == "Cerrado":
        return '<span class="tag tag-closed">CERRADO</span>'
    if stage == "Escalado":
        return '<span class="tag tag-esc">ESCALADO</span>'
    if stage == "Descartado":
        return '<span class="tag tag-disc">DESCARTADO</span>'
    last = p.get("last_decision") or ""
    colors = {"CONTINUAR": "tag-continuar", "FLAG": "tag-flag", "PIVOTAR": "tag-pivotar", "CERRAR": "tag-cerrar"}
    return f'<span class="tag {colors.get(last, "tag-seg")}">{html.escape(last or "EN SEGUIMIENTO")}</span>'


def render_stepper(p: dict, checkins: int):
    """Detectado → Plan → Kit → Seguimiento → Cerrado, with the current stage highlighted."""
    stage = db.pattern_stage(p, checkins)
    if stage in ("Descartado", "Escalado"):
        note = ("❌ Descartado: no se actuó sobre este patrón" if stage == "Descartado"
                else "⚠️ Escalado: necesita tu revisión directa")
        cls = "stp-off" if stage == "Descartado" else "stp-alert"
        st.markdown(f'<div class="stepper"><span class="stp {cls}">{note}</span></div>', unsafe_allow_html=True)
        return
    now = db.STAGES.index(stage)
    parts = []
    for i, name in enumerate(db.STAGES):
        cls = "stp-done" if i < now else "stp-now" if i == now else ""
        parts.append(f'<span class="stp {cls}">{name}</span>')
    st.markdown('<div class="stepper">' + '<span class="stp-arrow">→</span>'.join(parts) + '</div>',
                unsafe_allow_html=True)


def agent_line(text: str):
    st.markdown(f'<div class="agent-line">🤖 {html.escape(text)}</div>', unsafe_allow_html=True)


def render_tag(decision, extra_class=""):
    label, css_class, _ = TAG_MAP.get(
        decision,
        (decision or "Sin datos", "tag-default", "#DBDFE3")
    )
    return f'<span class="tag {css_class} {extra_class}">{label}</span>'


def match_decision(raw):
    raw = raw or ""
    if "CERRAR" in raw:
        return "CERRAR"
    elif "PIVOTAR" in raw:
        return "PIVOTAR"
    elif "CONTINUAR" in raw:
        return "CONTINUAR"
    elif "FLAG" in raw:
        return "FLAG"
    return "OTRO"


def extract_summary(narrative, evidence_summary, decision, cycle, max_sentences=2):
    """Short, readable summary of the latest check-in for the dashboard:
    1) the closing paragraph Outcome Check writes after its decision
       (CERRAR story, PIVOTAR hypothesis, or the adjustment to try),
    2) otherwise the last reasoning step it reached,
    3) otherwise a one-line status. Never the raw evidence dump."""
    def first_sentences(text):
        text = re.sub(r"\s+", " ", text).strip()
        sentences = re.split(r"(?<=[.!?])\s+", text)
        trimmed = " ".join(sentences[:max_sentences]).strip()
        return trimmed if trimmed.endswith((".", "!", "?")) else trimmed + "."

    narrative = narrative or ""
    if "Resumen para el club:" in narrative:
        return first_sentences(narrative.split("Resumen para el club:", 1)[1].lstrip("* "))

    lines = [l.strip() for l in narrative.split("\n") if l.strip()]
    after, last_step = [], ""
    seen_decision = False
    for line in lines:
        clean = re.sub(r"[#]", "", line).strip()
        plain = clean.replace("*", "")
        if re.match(r"Decisi[oó]n\s*(final)?\s*:", plain, re.I):
            seen_decision = True
            continue
        if seen_decision:
            after.append(clean)
            continue
        m = re.match(r"\**Paso\s*\d\s*[:.-]?\**\s*[:.-]?\s*(.*)", clean, re.I)
        if m and m.group(1):
            last_step = m.group(1)
    if after:
        return first_sentences(" ".join(after))
    if last_step:
        return first_sentences(last_step)

    decision_verb = {
        "CERRAR": "se confirmó resuelto",
        "CONTINUAR": "sigue en seguimiento",
        "PIVOTAR": "requirió un nuevo enfoque",
        "FLAG": "aún no tiene ejecución confirmada",
    }.get(decision, "fue evaluado")
    return f"En el seguimiento {cycle}, este patrón {decision_verb}."


def summary_html(text):
    """Escapes the text and turns **bold** into the lime highlight."""
    text = html.escape(text, quote=False)
    return re.sub(r"\*\*(.+?)\*\*", r'<strong class="hl">\1</strong>', text).replace("*", "")


def render_status_timeline(history):
    # Label each point by the owner's check-in number (per attempt), not by the
    # internal "executed cycles" counter, which stays at 0 until the action is done.
    counts, cycles = {}, []
    multiple_attempts = len({h.get("attempt") or 1 for h in history}) > 1
    for h in history:
        attempt = h.get("attempt") or 1
        counts[attempt] = counts.get(attempt, 0) + 1
        label = f"Seguimiento {counts[attempt]}"
        cycles.append(f"Intento {attempt} · {label}" if multiple_attempts else label)
    clean_decisions = [match_decision(h["decision"]) for h in history]
    colors = [TAG_MAP.get(d, ("", "", "#DBDFE3"))[2] for d in clean_decisions]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=list(range(len(cycles))),
            y=[0] * len(cycles),
            mode="lines+markers+text",
            line=dict(color="#DBDFE3", width=2),
            marker=dict(size=30, color=colors, line=dict(width=2, color="white")),
            text=clean_decisions,
            textposition="top center",
            textfont=dict(size=13, color="#030338"),
            hovertext=[f"{lbl}: {dec} · {str(h.get('created_at', ''))[8:10]}/{str(h.get('created_at', ''))[5:7]}/{str(h.get('created_at', ''))[:4]}"
                       for lbl, dec, h in zip(cycles, clean_decisions, history)],
            hoverinfo="text"
        )
    )

    fig.update_layout(
        height=170,
        showlegend=False,
        margin=dict(l=25, r=25, t=50, b=25),
        yaxis=dict(visible=False, range=[-1, 1.4]),
        xaxis=dict(
            tickmode="array",
            tickvals=list(range(len(cycles))),
            ticktext=cycles,
            showgrid=False,
            zeroline=False
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def render_pattern_detail(pattern):
    render_stepper(pattern, db.count_checkins(pattern["id"], pattern.get("attempt") or 1))
    _render_pattern_detail(pattern)


def _render_pattern_detail(pattern):
    """Timeline of check-ins (Outcome Check decisions) only. The other
    events in pattern_history (detected, plan approved, kit approved…)
    belong to the full Historial page."""
    history = (
        supabase.table("pattern_history")
        .select("*")
        .eq("pattern_id", pattern["id"])
        .eq("event_type", "check_in")
        .order("id")
        .execute()
        .data
    )

    if not history:
        if not pattern.get("verification_method"):
            st.caption("Este patrón espera su kit de ejecución. Genéralo en Kits de Ejecución.")
        else:
            st.caption("Aún no hay seguimientos. El primero aparecerá aquí tras revisar si la acción funcionó.")
        return

    render_status_timeline(history)

    current = history[-1]
    current_decision = match_decision(current["decision"])
    summary = extract_summary(
        current["narrative"],
        current["evidence_summary"],
        current_decision,
        len(history)
    )

    # What changed since the last check-in, so the summary isn't misread
    pattern_attempt = pattern.get("attempt") or 1
    if pattern.get("status") == "escalated":
        st.markdown('<div class="status-note status-escalated">⚠️ Escalado: después de varios intentos, '
                    'este patrón necesita tu revisión directa.</div>', unsafe_allow_html=True)
    elif pattern_attempt > (current.get("attempt") or 1):
        next_step = ("pendiente de su kit en Kits de Ejecución" if not pattern.get("verification_method")
                     else "en seguimiento")
        st.markdown(f'<div class="status-note">🔄 Nuevo enfoque aprobado (intento {pattern_attempt}): '
                    f'{next_step}. El resumen de abajo es del intento anterior.</div>', unsafe_allow_html=True)

    st.markdown(f'<div class="summary-box">{summary_html(summary)}</div>', unsafe_allow_html=True)

    if st.button("Ver historial completo →", key=f"hist_{pattern['id']}", type="secondary"):
        st.session_state["hist_pattern"] = pattern["id"]
        try:
            st.switch_page("pages/5_Historial.py")
        except Exception:
            st.caption("Abre **Historial** en el menú lateral.")


st.title("🎾 Dashboard — Club de Pádel")
render_journey(0)
agent_line("Sistema de 4 agentes: Insights · Action Planning · Execution Kit · Outcome Check")
st.caption("Vista general del sistema de mejora continua")

# ---------------------------------------------------------------------------
# Tu siguiente paso — what needs the owner now, with a button to each step
# ---------------------------------------------------------------------------

counts = db.get_journey_counts()
days = counts.get("days_since_analysis")
analysis_text = ("Aún no has analizado las opiniones del club." if days is None
                 else "Último análisis hoy." if days == 0
                 else f"Último análisis hace {days} día(s).")
pending_plan = counts.get("pending_plan", 0)
if pending_plan:
    detect_tile = ("detect", "🔍 1 · Detectar", True, pending_plan,
                   "patrón(es) detectados esperan su recomendación. Revísalos uno a uno.",
                   "Revisar recomendaciones →", PAGE_PATHS["Detectar"])
else:
    detect_tile = ("detect", "🔍 1 · Detectar", days is None or days >= 7,
                   days if days is not None else "—", analysis_text + " Lo habitual es cada semana.",
                   "Analizar →", PAGE_PATHS["Detectar"])
tiles = [
    detect_tile,
    ("kits", "📋 2 · Preparar", counts["pending_kit"] > 0,
     counts["pending_kit"], "plan(es) esperan su kit de ejecución.",
     "Preparar kits →", PAGE_PATHS["Preparar"]),
    ("follow", "🔁 3 · Seguir", counts["due_checkins"] > 0,
     counts["due_checkins"], "patrón(es) toca revisar (sin seguimiento o hace más de 2 semanas).",
     "Hacer seguimiento →", PAGE_PATHS["Seguir"]),
    ("esc", "⚠️ Escalados", counts["escalated"] > 0,
     counts["escalated"], "patrón(es) necesitan tu revisión directa.",
     "Ver historial →", PAGE_PATHS["Historial"]),
]
st.subheader("Tu siguiente paso")
cols = st.columns(4)
for col, (key, title, hot, count, text, button, path) in zip(cols, tiles):
    with col:
        with st.container(key=f"next_{'hot_' if hot else ''}{key}"):
            st.markdown(
                f'<div class="next-title">{title}</div>'
                f'<div class="next-count">{count}</div>'
                f'<div class="next-text">{html.escape(text)}</div>',
                unsafe_allow_html=True,
            )
            if st.button(button, key=f"next_btn_{key}", type="primary" if hot else "secondary"):
                go_to_page(path)

st.divider()

result = supabase.table("patterns").select("*").order("id").execute()
# Discarded recommendations stay in Supabase (so Insights remembers them)
# but they aren't patterns the club is working on, so they're not shown here.
patterns = [p for p in (result.data or []) if p.get("status") != "discarded"]

total = len(patterns)
# "En seguimiento activo" = open AND with an approved kit (pending-kit plans aren't followed yet)
open_count = len([p for p in patterns if p.get("status") == "open" and p.get("verification_method")])
closed_count = len([p for p in patterns if p.get("status") == "closed"])
attention_count = len([
    p for p in patterns
    if p.get("last_decision") == "FLAG" or p.get("status") == "escalated"
])

st.subheader("Estado actual de cada patrón")
col1, col2, col3, col4 = st.columns(4)
col1.metric("📊 Patrones totales", total)
col2.metric("🟢 Cerrados", closed_count)
col3.metric("🔄 En seguimiento activo", open_count)
col4.metric("🚩 Requieren atención", attention_count)

if "expanded_pattern" not in st.session_state:
    st.session_state.expanded_pattern = None

if not patterns:
    st.info("Aún no hay patrones registrados.")
else:
    for p in patterns:
        is_open = st.session_state.expanded_pattern == p["id"]
        card_key = f"pattern_open_{p['id']}" if is_open else f"pattern_card_{p['id']}"

        with st.container(key=card_key):
            col_a, col_b, col_c = st.columns([4, 2, 1], vertical_alignment="center")

            with col_a:
                st.markdown(
                    f'<div class="pattern-name">{html.escape(p["pattern_name"])}</div>',
                    unsafe_allow_html=True
                )

            with col_b:
                st.markdown(stage_tag(p, db.count_checkins(p["id"], p.get("attempt") or 1)),
                            unsafe_allow_html=True)

            with col_c:
                if st.button("Ver detalle →", key=f"btn_{p['id']}", type="primary"):
                    st.session_state.expanded_pattern = (
                        None if st.session_state.expanded_pattern == p["id"] else p["id"]
                    )
                    st.rerun()

            if is_open:
                st.divider()
                render_pattern_detail(p)

st.divider()

# Gemini usage in the last 7 days (logged by agents/llm.py) — owner only (access matrix)
try:
    usage = db.get_llm_usage(7) if can("coste_gemini") else None
except Exception:
    usage = None
if usage and usage["calls"]:
    line = (f"🤖 Uso de Gemini (últimos 7 días): {usage['calls']} llamadas · "
            f"{usage['seconds'] / 60:.1f} min · {usage['tokens']:,} tokens".replace(",", "."))
    if usage["cost_usd"] is not None:
        line += f" · ~${usage['cost_usd']:.2f}"
    if usage["errors"] or usage["retried"]:
        line += f" · {usage['retried']} reintentada(s), {usage['errors']} fallida(s)"
    with st.expander(line):
        rows = sorted(usage["per_agent"].items(), key=lambda kv: -kv[1]["calls"])
        st.markdown("\n".join(
            f"- **{agent}**: {v['calls']} llamadas · {v['seconds']:.0f} s · "
            f"{(v['seconds'] / v['calls']):.1f} s de media · {v['tokens']:,} tokens".replace(",", ".")
            for agent, v in rows
        ))

# Last weekly summary (scripts/weekly_run.py)
try:
    last = db.get_last_notification()
except Exception:
    last = None
if last:
    sent = {"sent": "enviado por WhatsApp", "not_sent": "guardado (WhatsApp sin configurar)",
            "error": "no se pudo enviar"}.get(last.get("status"), last.get("status"))
    when = str(last.get("created_at") or "")[:10]
    with st.expander(f"📬 Último resumen semanal · {when} · {sent}"):
        st.text(last.get("body") or "")
        if last.get("error"):
            st.caption(f"Detalle: {last['error']}")

st.caption("Datos en tiempo real desde Supabase.")