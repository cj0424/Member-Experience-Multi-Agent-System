"""
Quick test to confirm the Gemini API key works before building
any real logic on top of it.
"""

import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

response = client.models.generate_content(
    model="gemini-3.7-flash",
    contents="Say hello in one short sentence."
)
print(response.text)