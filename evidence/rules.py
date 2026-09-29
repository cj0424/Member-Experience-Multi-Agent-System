"""
All numbers used to decide what becomes a pattern, in one place.
Documented in docs/insights-pattern-rules.md. Change them here only.
"""

# --- Sources ---
CLUB_SOURCES = {"survey", "incident", "staff"}
ALL_SOURCES = CLUB_SOURCES | {"google"}

# --- Windows (days) ---
WINDOW_CLUB_DAYS = 28          # club sources: last 28 days up to the run date
WINDOW_GOOGLE_DAYS = 365       # Google reviews: last 12 months, only alongside club evidence
SLOW_RULE_DAYS = 90            # slow rule look-back

# --- Main rule ---
MIN_DISTINCT_DATES = 2         # mentions on at least 2 different dates
MIN_TOTAL_MENTIONS = 3         # at least 3 mentions (all sources together) ...
MIN_SOURCE_TYPES = 2           # ... OR at least 2 of the 4 source types

# --- Slow rule ---
SLOW_RULE_MIN_WEEKS = 3        # mentions in 3 different calendar weeks within 90 days
                               # (most recent within 28 days, club sources only)

# --- Scoring (each factor 1 = least, 3 = most) ---
# Frequency: number of mentions used as evidence
FREQUENCY_BANDS = [(6, 3), (3, 2), (1, 1)]          # 6+ -> 3, 3-5 -> 2, 1-2 -> 1
# Recency: days since the most recent CLUB mention (0 = run date)
RECENCY_BANDS = [(6, 3), (13, 2), (27, 1)]          # last 7 days -> 3, 8-14 -> 2, 15-28 -> 1
SLOW_RULE_RECENCY_DEFAULT = 1
# Priority = 2 x severity + reach + frequency + recency  (5-15)
PRIORITY_BANDS = [(12, "Alta"), (9, "Media"), (5, "Baja")]
SAFETY_SEVERITY = 3            # severity 3 -> always Alta + immediate alert

# --- Confidence ---
CONFIDENCE_HIGH_MIN_SOURCES = 3
CONFIDENCE_HIGH_MIN_MENTIONS = 6

# --- A vigilar ---
WATCH_MIN_MENTIONS = 2         # 2+ mentions that don't meet the rule
WATCH_SINGLE_MIN_SEVERITY = 2  # or 1 mention of severity 2

# --- Topics: the only topics Gemini may use ---
# severity: 1 comfort, 2 playing conditions / broken service, 3 safety (set per mention)
# reach:    1 a few people, 2 a group (one court, slot, class), 3 almost everyone
TOPICS = {
    "aparcamiento":         {"label": "Aparcamiento",                     "severity": 1, "reach": 3},
    "arena_pistas":         {"label": "Arena en las pistas",              "severity": 2, "reach": 2},
    "estado_pistas":        {"label": "Estado general de las pistas",     "severity": 2, "reach": 3},
    "iluminacion_pista":    {"label": "Iluminación de una pista",         "severity": 2, "reach": 2},
    "luces_exteriores":     {"label": "Luces fuera de las pistas",        "severity": 1, "reach": 3},
    "temperatura_interior": {"label": "Temperatura dentro del club",      "severity": 1, "reach": 3},
    "techos_bajos":         {"label": "Altura de los techos",             "severity": 1, "reach": 2},
    "agua_caliente":        {"label": "Agua caliente en las duchas",      "severity": 2, "reach": 3},
    "toallas":              {"label": "Toallas en vestuarios",            "severity": 1, "reach": 2},
    "averia_vestuario":     {"label": "Averías en vestuarios o aseos",    "severity": 2, "reach": 2},
    "limpieza":             {"label": "Limpieza",                         "severity": 1, "reach": 3},
    "maquina_bebidas":      {"label": "Máquina de bebidas / cafetería",   "severity": 1, "reach": 2},
    "retrasos_reservas":    {"label": "Retrasos en el cambio de pista",   "severity": 2, "reach": 2},
    "reservas_playtomic":   {"label": "Problemas al reservar",            "severity": 2, "reach": 3},
    "musica_volumen":       {"label": "Volumen de la música",             "severity": 1, "reach": 2},
    "red_puertas":          {"label": "Redes o puertas de las pistas",    "severity": 2, "reach": 2},
    "clases_profesores":    {"label": "Clases y profesores",              "severity": 2, "reach": 2},
    "plazas_clases":        {"label": "Plazas y listas de espera en clases", "severity": 2, "reach": 2},
    "personal_recepcion":   {"label": "Atención en recepción",            "severity": 1, "reach": 3},
    "ambiente":             {"label": "Ambiente del club",                "severity": 1, "reach": 3},
    "instalaciones":        {"label": "Instalaciones en general",         "severity": 1, "reach": 3},
    "precio":               {"label": "Precio",                           "severity": 1, "reach": 3},
    "objetos_perdidos":     {"label": "Objetos perdidos",                 "severity": 1, "reach": 1},
    "otro":                 {"label": "Otro",                             "severity": 1, "reach": 1},
}

# Logged, but never a pattern (not something members experience as a problem)
EXCLUDED_TOPICS = {"objetos_perdidos", "otro"}
