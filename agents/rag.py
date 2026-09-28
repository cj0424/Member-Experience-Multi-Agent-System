"""
rag.py — the shared RAG library, read the same way by every agent that
needs it (Action Planning, Execution Kit, Outcome Check).

data/rag_library/ holds two kinds of documents:
- Technical and best-practice references (maintenance norms, loyalty
  best practices…). Agents can cite these as a "Fuente".
- club_profile.txt — how THIS club works inside: staff, shifts, rules,
  tools, channels, budget. Not a citable source: it's context, so every
  plan, kit and follow-up fits the club's real way of working.

Keeping them apart means the profile is always included, but never shows
up as a "Fuente" in a recommendation.
"""

import glob
import os

RAG_FOLDER = "data/rag_library"
CLUB_PROFILE_FILE = "club_profile.txt"


def load_rag_library(folder_path: str = RAG_FOLDER) -> str:
    """Every technical / best-practice document, labeled by file name so
    Gemini can judge relevance and cite it. The club profile is excluded
    here — it's loaded separately by load_club_profile()."""
    combined = []
    for filepath in sorted(glob.glob(f"{folder_path}/*.txt")):
        filename = os.path.basename(filepath)
        if filename == CLUB_PROFILE_FILE:
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            combined.append(f"--- FUENTE: {filename} ---\n{f.read()}")
    return "\n\n".join(combined)


def load_club_profile(folder_path: str = RAG_FOLDER) -> str:
    """How this specific club works. Without it, agents guess — and
    guesses about tools, staff and rules are what make plans unfeasible."""
    try:
        with open(os.path.join(folder_path, CLUB_PROFILE_FILE), "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "No disponible."