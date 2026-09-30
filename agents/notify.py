"""
notify.py — delivers the weekly summary (Phase 3).

Channel chosen in .env with NOTIFY_CHANNEL:
- telegram (the demo channel): a Telegram bot sends the message to one chat.
      TELEGRAM_BOT_TOKEN   from @BotFather
      TELEGRAM_CHAT_ID     find it with: python scripts/telegram_chat_id.py
- whatsapp (the production channel for a Spanish club): WhatsApp Cloud API.
      WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_TO, WHATSAPP_API_VERSION (optional)
      Note: a business can only START a WhatsApp conversation with an approved
      template; plain text is delivered only within 24 h of the recipient writing.
Without a configured channel nothing is sent: the message is still saved in
Supabase (notifications) and shown on the Dashboard.
"""

import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()


def channel() -> str:
    return (os.getenv("NOTIFY_CHANNEL") or "telegram").strip().lower()


def configured() -> bool:
    if channel() == "whatsapp":
        return all(os.getenv(k) for k in ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_TO"))
    return all(os.getenv(k) for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"))


def _post(url: str, payload: dict, headers: dict | None = None) -> tuple[bool, str | None]:
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                     headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return 200 <= response.status < 300, None
    except urllib.error.HTTPError as e:
        return False, f"{e.code}: {e.read().decode(errors='ignore')[:300]}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def send(text: str) -> tuple[bool, str | None]:
    """Sends through the configured channel. Returns (sent, error_message)."""
    if not configured():
        return False, f"{channel()} no está configurado (.env)"
    if channel() == "whatsapp":
        version = os.getenv("WHATSAPP_API_VERSION", "v23.0")
        ok, err = _post(
            f"https://graph.facebook.com/{version}/{os.getenv('WHATSAPP_PHONE_NUMBER_ID')}/messages",
            {"messaging_product": "whatsapp", "to": os.getenv("WHATSAPP_TO"),
             "type": "text", "text": {"preview_url": False, "body": text[:4000]}},
            {"Authorization": f"Bearer {os.getenv('WHATSAPP_TOKEN')}"})
        return ok, (f"WhatsApp {err}" if err else None)
    ok, err = _post(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage",
                    {"chat_id": os.getenv("TELEGRAM_CHAT_ID"), "text": text[:4000],
                     "disable_web_page_preview": True})
    return ok, (f"Telegram {err}" if err else None)
