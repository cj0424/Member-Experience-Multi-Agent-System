"""
notify.py — sends the weekly summary (Phase 3).

WhatsApp is the club's channel (club_profile.txt), so messages go through
the WhatsApp Cloud API when it's configured in .env:
    WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_TO (e.g. 34600111222)
    WHATSAPP_API_VERSION (optional; use the version shown in your Meta dashboard)
Without them, nothing is sent: the message is still saved in Supabase
(notifications) and shown on the Dashboard, so the flow can be tested first.

Note: WhatsApp only lets a business start a conversation with an approved
TEMPLATE. A plain text like this one is delivered only within 24 hours of the
recipient writing to the business number. For a demo, write to the test
number first; for production, the weekly message becomes an approved template.
"""

import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()


def whatsapp_configured() -> bool:
    return all(os.getenv(k) for k in ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_TO"))


def send_whatsapp(text: str) -> tuple[bool, str | None]:
    """Returns (sent, error_message)."""
    if not whatsapp_configured():
        return False, "WhatsApp no está configurado (.env)"
    version = os.getenv("WHATSAPP_API_VERSION", "v23.0")
    url = f"https://graph.facebook.com/{version}/{os.getenv('WHATSAPP_PHONE_NUMBER_ID')}/messages"
    body = json.dumps({
        "messaging_product": "whatsapp", "to": os.getenv("WHATSAPP_TO"),
        "type": "text", "text": {"preview_url": False, "body": text[:4000]},
    }).encode()
    request = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {os.getenv('WHATSAPP_TOKEN')}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return 200 <= response.status < 300, None
    except urllib.error.HTTPError as e:
        return False, f"WhatsApp {e.code}: {e.read().decode(errors='ignore')[:300]}"
    except Exception as e:  # noqa: BLE001
        return False, f"WhatsApp: {e}"
