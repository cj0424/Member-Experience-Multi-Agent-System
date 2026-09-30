"""
Finds your Telegram chat ID for the weekly summary (Phase 3).

1. Put TELEGRAM_BOT_TOKEN in .env (from @BotFather).
2. Open your bot in Telegram and send it any message (e.g. "hola").
3. Run:  python scripts/telegram_chat_id.py
It prints the line to add to .env. The token never leaves your computer.
"""
import json
import os
import sys
import urllib.request

from dotenv import load_dotenv

load_dotenv()
token = os.getenv("TELEGRAM_BOT_TOKEN")
if not token:
    sys.exit("Falta TELEGRAM_BOT_TOKEN en el .env")

with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20) as r:
    updates = json.loads(r.read().decode()).get("result", [])

chats = {}
for u in updates:
    chat = (u.get("message") or u.get("edited_message") or {}).get("chat")
    if chat:
        chats[chat["id"]] = chat.get("first_name") or chat.get("title") or ""

if not chats:
    sys.exit("No encuentro mensajes. Abre tu bot en Telegram, envíale 'hola' y vuelve a ejecutar esto.")
for chat_id, name in chats.items():
    print(f"TELEGRAM_CHAT_ID={chat_id}    ({name})")
print("\nCopia la línea TELEGRAM_CHAT_ID=... en tu .env")
