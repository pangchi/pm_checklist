"""
telegram_alert.py — Send startup alert via Telegram Bot API.
"""

import socket
import urllib.request
import urllib.parse
import urllib.error
import json
import logging

logger = logging.getLogger(__name__)


def _get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "unknown"


def _get_public_ip():
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=5) as r:
            return r.read().decode().strip()
    except Exception:
        return None


def send_startup_alert(bot_token: str, chat_id: str, app_port: int = 5000):
    """Send a Telegram message with hostname and IP info on startup."""
    if not bot_token or not chat_id:
        logger.warning("[Telegram] bot_token or chat_id not configured — skipping alert.")
        return False

    hostname = socket.gethostname()
    local_ip = _get_local_ip()
    public_ip = _get_public_ip()

    lines = [
        "🟢 *PM Checklist — Server Started*",
        "",
        f"🖥 Hostname: `{hostname}`",
        f"🔌 Local IP: `{local_ip}:{app_port}`",
    ]
    if public_ip:
        lines.append(f"🌐 Public IP: `{public_ip}`")
    lines += [
        "",
        f"🔗 Access: `http://{local_ip}:{app_port}`",
    ]

    text = "\n".join(lines)
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
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
                logger.info(f"[Telegram] Startup alert sent to chat {chat_id}.")
                return True
            else:
                logger.warning(f"[Telegram] API returned not-ok: {body}")
                return False
    except urllib.error.URLError as e:
        logger.warning(f"[Telegram] Failed to send alert: {e}")
        return False
    except Exception as e:
        logger.warning(f"[Telegram] Unexpected error: {e}")
        return False
