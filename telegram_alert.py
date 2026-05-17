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

    local_url = f"http://{local_ip}:{app_port}"

    lines = [
        "🟢 <b>PM Checklist — Server Started</b>",
        "",
        f"🖥 Hostname: <code>{hostname}</code>",
        f"🔌 Local IP: <code>{local_ip}:{app_port}</code>",
    ]
    if public_ip:
        lines.append(f"🌐 Public IP: <code>{public_ip}</code>")
    lines += [
        "",
        f'🔗 Access: <a href="{local_url}">{local_url}</a>',
    ]
    if public_ip:
        public_url = f"http://{public_ip}:{app_port}"
        lines.append(f'🌍 Public: <a href="{public_url}">{public_url}</a>')

    text = "\n".join(lines)
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
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


def send_telegram_message(bot_token: str, chat_id: str, html_text: str) -> bool:
    """Send any HTML-formatted message via Telegram. Returns True on success."""
    if not bot_token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": html_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
            return bool(body.get("ok"))
    except Exception as e:
        logger.warning(f"[Telegram] send_telegram_message failed: {e}")
        return False
