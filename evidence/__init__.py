"""Multi-source evidence for the Insights agent (Phase 3).

rules.py    all pattern-rule numbers and topic defaults, in one place
loaders.py  reads the four sources into one common shape
store.py    saves evidence, tags and source runs in Supabase
tagging.py  Gemini tags each entry (topic, complaint or praise, safety)
engine.py   counts, applies the rules, scores and ranks (no LLM)
"""
