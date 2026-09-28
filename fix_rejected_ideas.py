"""
fix_rejected_ideas.py — one-off clean-up of patterns.rejected_ideas.

Before the fix in db.py, a "Pedir cambios" could record as rejected:
- options the owner KEPT in the approved plan (e.g. staggering the courts);
- section titles that aren't ideas ("El punto de partida", "Qué puedes
  hacer para…").
This script shows, for each pattern, the list before and after cleaning,
and only saves if you confirm. Run it once, from the project folder:

    python fix_rejected_ideas.py
"""

import os
import re
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents"))

import db

SECTION_TITLE = re.compile(
    r"^(el |la |lo )?(punto de partida|problema|situaci[oó]n|oportunidad|momento|"
    r"qu[eé] (se )?puede|qu[eé] puedes|qu[eé] podemos|por qu[eé]|vale la pena|"
    r"opciones|c[oó]mo aprovech)",
    re.I,
)


def drop_section_titles(rejected_text: str | None) -> str | None:
    if not rejected_text:
        return rejected_text
    lines = []
    for line in rejected_text.split("\n"):
        m = db.REJECTED_LINE.match(line)
        if not m:
            if line.strip():
                lines.append(line)
            continue
        prefix, titles, reason = m.group(1) or "", m.group(2), m.group(3)
        ideas = [t.strip() for t in titles.split(";")
                 if t.strip() and not SECTION_TITLE.match(t.strip().strip("'\""))]
        if ideas:
            lines.append(f"{prefix}Descartado: {'; '.join(ideas)} {reason}")
    return "\n".join(lines) or None


def main():
    changes = []
    for p in db.get_all_patterns():
        before = p.get("rejected_ideas")
        if not before:
            continue
        after = drop_section_titles(before)
        if p.get("approved_action") and p.get("status") != "discarded":
            after = db.drop_kept_ideas(after, p["approved_action"])
        if (after or "") != (before or ""):
            changes.append((p, before, after))

    if not changes:
        print("✅ Nada que limpiar: todas las listas de ideas descartadas están bien.")
        return

    for p, before, after in changes:
        print(f"\n=== #{p['id']} {p['pattern_name']} ===")
        print("ANTES:\n" + before)
        print("DESPUÉS:\n" + (after or "(vacío)"))

    answer = input("\n¿Guardar estos cambios en Supabase? (s/n): ").strip().lower()
    if answer != "s":
        print("No se ha guardado nada.")
        return
    for p, _, after in changes:
        db.update_pattern(p["id"], {"rejected_ideas": after})
    print(f"✅ Guardado: {len(changes)} patrón(es) limpiado(s).")


if __name__ == "__main__":
    main()