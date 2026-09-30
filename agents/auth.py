"""
auth.py — Google login (SSO) + access matrix + "Ver como" (Phase 3).

Authentication (who are you?): Google login through Streamlit's st.login().
No passwords in the app. Setup lives in .streamlit/secrets.toml ([auth]).

Authorization (what can you do?): the ACCESS MATRIX below, like a role/ACL
matrix in ServiceNow. Each email is mapped to one role in .env or secrets:
    APP_ROLE_PROPIETARIO=you@gmail.com
    APP_ROLE_GERENTE=manager@gmail.com        (optional; comma-separated lists work)
An email that isn't mapped can log in with Google but gets no access.
Staff (reception, maintenance, coaches) don't log in: they contribute
through the incident log and the staff notes, which reach the system as sources.

"Ver como" (impersonation): the owner can preview the app exactly as the
manager sees it, like ServiceNow's "Impersonate user". Actions taken while
impersonating are recorded honestly: "Propietario (como Gerente)".
"""

import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

ROLES = {"propietario": "Propietario", "gerente": "Gerente"}

# The access matrix: permission → roles that have it
ACCESS_MATRIX = {
    "ver":            {"label": "Ver Dashboard, Historial y usar Pala",                      "roles": {"propietario", "gerente"}},
    "detectar":       {"label": "Ejecutar el análisis y aprobar, revisar o descartar planes", "roles": {"propietario", "gerente"}},
    "preparar":       {"label": "Generar y aprobar kits",                                    "roles": {"propietario", "gerente"}},
    "seguir":         {"label": "Hacer seguimientos",                                        "roles": {"propietario", "gerente"}},
    "coste_gemini":   {"label": "Ver el uso y el coste de Gemini",                            "roles": {"propietario"}},
    "matriz_accesos": {"label": "Ver la matriz de accesos",                                   "roles": {"propietario"}},
    "ver_como":       {"label": "Ver la app como otro rol",                                   "roles": {"propietario"}},
}


def _setting(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    try:
        return str(st.secrets.get(name, "") or "")
    except Exception:  # noqa: BLE001
        return ""


def _emails_for(role: str) -> set[str]:
    raw = _setting(f"APP_ROLE_{role.upper()}")
    return {e.strip().lower() for e in raw.replace(";", ",").split(",") if e.strip()}


def _logged_in_email() -> str | None:
    try:
        if st.user.is_logged_in:
            return (st.user.get("email") or "").lower() or None
    except Exception:  # noqa: BLE001 - auth not configured
        return None
    return None


def real_role() -> str | None:
    email = _logged_in_email()
    if not email:
        return None
    for role in ROLES:
        if email in _emails_for(role):
            return role
    return None


def effective_role() -> str | None:
    role = real_role()
    if role == "propietario" and st.session_state.get("ver_como") == "gerente":
        return "gerente"
    return role


def can(permission: str) -> bool:
    role = effective_role()
    return bool(role) and role in ACCESS_MATRIX[permission]["roles"]


def actor_label() -> str:
    """Who is acting, for the history: 'Gerente', 'Propietario' or 'Propietario (como Gerente)'."""
    real, eff = real_role(), effective_role()
    if not real:
        return "—"
    if eff != real:
        return f"{ROLES[real]} (como {ROLES[eff]})"
    return ROLES[real]


def is_authorized() -> bool:
    return real_role() is not None


def _auth_configured() -> bool:
    try:
        return "auth" in st.secrets
    except Exception:  # noqa: BLE001
        return False


def _login_screen():
    st.markdown("### 🔐 Club de Pádel — acceso")
    if not _auth_configured():
        st.error("El inicio de sesión con Google aún no está configurado: falta la sección [auth] "
                 "en .streamlit/secrets.toml.")
        st.stop()
    st.write("Entra con tu cuenta de Google.")
    st.button("Iniciar sesión con Google", type="primary", on_click=st.login)
    st.stop()


def _sidebar():
    real, eff = real_role(), effective_role()
    with st.sidebar:
        st.caption(f"👤 {_logged_in_email()} · **{ROLES[real]}**")
        if real == "propietario":
            viewing = st.toggle("👁️ Ver como Gerente", value=st.session_state.get("ver_como") == "gerente",
                                key="ver_como_toggle")
            wanted = "gerente" if viewing else None
            if st.session_state.get("ver_como") != wanted:
                st.session_state["ver_como"] = wanted
                st.rerun()
        if can("matriz_accesos"):
            with st.expander("🔐 Permisos"):
                for perm in ACCESS_MATRIX.values():
                    marks = " · ".join(f"{ROLES[r]} {'✅' if r in perm['roles'] else '❌'}" for r in ROLES)
                    st.markdown(f"**{perm['label']}**  \n{marks}")
                st.caption("El personal no inicia sesión: aporta por el registro de incidencias y las notas del personal.")
        st.button("Cerrar sesión", key="auth_logout", on_click=st.logout)
    if eff != real:
        st.info(f"👁️ Viendo la app como **{ROLES[eff]}**. Lo que hagas se registra como “{actor_label()}”.")


def require_login(permission: str = "ver") -> str:
    """Call right after st.set_page_config on every page. Stops the page until the
    user logs in with Google and has `permission` in the access matrix."""
    email = _logged_in_email()
    if not email:
        _login_screen()
    if not real_role():
        st.warning(f"Has iniciado sesión como {email}, pero no tienes acceso a esta app. "
                   "Pide al propietario que te añada.")
        st.button("Cerrar sesión", on_click=st.logout)
        st.stop()
    _sidebar()
    if not can(permission):
        st.warning(f"No tienes permiso para esta página ({ACCESS_MATRIX[permission]['label'].lower()}).")
        st.stop()
    return effective_role()
