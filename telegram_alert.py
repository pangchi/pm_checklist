"""
telegram_alert.py — Send startup and purge alerts via Telegram Bot API.

All dynamic values passed into HTML messages are HTML-escaped before sending.
Telegram parse_mode="HTML" rejects messages containing unescaped < > & characters
in text nodes, even inside <code> tags.
"""

import socket
import urllib.request
import urllib.parse
import urllib.error
import json
import logging
from html import escape as _esc   # stdlib — escapes &, <, >, "

logger = logging.getLogger(__name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "unknown"


def _get_public_ip() -> str | None:
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=5) as r:
            return r.read().decode().strip()
    except Exception:
        return None


def _send(bot_token: str, chat_id: str, html_text: str) -> bool:
    """
    Core send function. Logs the full Telegram error description on failure.
    html_text must already have all dynamic values HTML-escaped.
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": html_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
            if body.get("ok"):
                return True
            # Telegram returned ok=false — log the description
            desc = body.get("description", "no description")
            logger.warning(f"[Telegram] API error: {body.get('error_code')} — {desc}")
            return False
    except urllib.error.HTTPError as e:
        # Read the body to get Telegram's error message
        try:
            err_body = json.loads(e.read())
            desc = err_body.get("description", str(e))
        except Exception:
            desc = str(e)
        logger.warning(f"[Telegram] HTTP {e.code}: {desc}")
        return False
    except urllib.error.URLError as e:
        logger.warning(f"[Telegram] Network error: {e.reason}")
        return False
    except Exception as e:
        logger.warning(f"[Telegram] Unexpected error: {e}")
        return False


# ─── Public API ───────────────────────────────────────────────────────────────

def send_startup_alert(bot_token: str, chat_id: str, app_port: int = 5000) -> bool:
    """Send hostname + IP info on server startup."""
    if not bot_token or not chat_id:
        logger.info("[Telegram] Credentials not configured — skipping startup alert.")
        return False

    hostname  = _esc(socket.gethostname())
    local_ip  = _esc(_get_local_ip())
    public_ip = _get_public_ip()
    local_url = f"http://{local_ip}:{app_port}"

    lines = [
        "🟢 <b>PM Checklist — Server Started</b>",
        "",
        f"🖥 Hostname: <code>{hostname}</code>",
        f"🔌 Local IP: <code>{local_ip}:{app_port}</code>",
    ]
    if public_ip:
        lines.append(f"🌐 Public IP: <code>{_esc(public_ip)}</code>")
    lines += [
        "",
        f'🔗 Access: <a href="{local_url}">{local_url}</a>',
    ]
    if public_ip:
        public_url = f"http://{_esc(public_ip)}:{app_port}"
        lines.append(f'🌍 Public: <a href="{public_url}">{public_url}</a>')

    ok = _send(bot_token, chat_id, "\n".join(lines))
    if ok:
        logger.info(f"[Telegram] Startup alert sent to chat {chat_id}.")
    return ok


def send_telegram_message(bot_token: str, chat_id: str, html_text: str) -> bool:
    """
    Send a pre-formatted HTML message. Caller is responsible for escaping
    any dynamic values using html.escape() before embedding in html_text.
    """
    if not bot_token or not chat_id:
        return False
    ok = _send(bot_token, chat_id, html_text)
    if not ok:
        logger.warning("[Telegram] send_telegram_message failed — see above for details.")
    return ok
