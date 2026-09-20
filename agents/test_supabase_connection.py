"""
Quick test to confirm Supabase connection and table access work
before wiring real data into Agent 4.
"""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

supabase = create_client(url, key)

# Insert one test row
result = supabase.table("patterns").insert({
    "pattern_name": "Test connection — safe to delete",
    "approved_action": "N/A",
    "verification_method": "N/A",
    "verification_result": "N/A",
    "status": "test"
}).execute()

print("Inserted:", result.data)

# Read it back
check = supabase.table("patterns").select("*").eq("status", "test").execute()
print("\nRead back:", check.data)