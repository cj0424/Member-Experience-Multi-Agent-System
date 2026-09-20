"""
Quick test to confirm get_pattern_from_db correctly reads the
real pattern row we just inserted into Supabase.
"""

from outcome_check_agent import get_pattern_from_db

pattern = get_pattern_from_db("Exceso de arena en las pistas")
print(pattern)