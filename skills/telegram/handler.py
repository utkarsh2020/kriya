"""
AgentOS skill – Telegram
Sends and reads messages via the Telegram Bot API.
Pure stdlib: urllib.request only. No external dependencies.

Secrets (set via: agent secret set --project <p> --key <K>):
  TELEGRAM_BOT_TOKEN  — Bot token from @BotFather
  TELEGRAM_CHAT_ID    — Default chat/channel ID (optional; can be passed per-call)
"""
import json
import urllib.request
import urllib.error

SKILL_ID = "telegram.send"
SKILL_VERSION = "1.0.0"

_API = "https://api.telegram.org/bot{token}/{method}"


def _call(token: str, method: str, payload: dict) -> dict:
    url  = _API.format(token=token, method=method)
    body = json.dumps(payload).encode()
    req  = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": e.read().decode(errors="replace")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def handle(params: dict, secrets: dict) -> dict:
    """
    Send a Telegram message (and optionally receive recent messages).

    params:
      action    : "send" (default) | "get_updates"
      text      : Message text (required for send)
      chat_id   : Override default chat ID (optional for send)
      parse_mode: "HTML" | "Markdown" | "MarkdownV2" (optional, default plain)
      offset    : Update offset for get_updates (optional)
      limit     : Max updates to fetch, 1-100 (default 10)

    secrets:
      TELEGRAM_BOT_TOKEN  — required
      TELEGRAM_CHAT_ID    — default target chat (used when chat_id not in params)
    """
    token = secrets.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return {"error": "TELEGRAM_BOT_TOKEN secret not set"}

    action = params.get("action", "send")

    if action == "get_updates":
        payload: dict = {"timeout": 0}
        if "offset" in params:
            payload["offset"] = int(params["offset"])
        payload["limit"] = min(int(params.get("limit", 10)), 100)
        result = _call(token, "getUpdates", payload)
        if not result.get("ok"):
            return {"error": result.get("error", "Telegram API error"), "raw": result}
        updates = result.get("result", [])
        messages = [
            {
                "update_id": u["update_id"],
                "message_id": u["message"]["message_id"],
                "from": u["message"].get("from", {}).get("username"),
                "chat_id": u["message"]["chat"]["id"],
                "text": u["message"].get("text", ""),
                "date": u["message"]["date"],
            }
            for u in updates
            if "message" in u
        ]
        return {"ok": True, "messages": messages, "count": len(messages)}

    # Default: send message
    chat_id = params.get("chat_id") or secrets.get("TELEGRAM_CHAT_ID", "").strip()
    if not chat_id:
        return {"error": "chat_id required (pass in params or set TELEGRAM_CHAT_ID secret)"}

    text = params.get("text", "").strip()
    if not text:
        return {"error": "text required for send action"}

    payload = {"chat_id": chat_id, "text": text}
    if "parse_mode" in params:
        payload["parse_mode"] = params["parse_mode"]

    result = _call(token, "sendMessage", payload)
    if not result.get("ok"):
        return {"error": result.get("description", "Telegram API error"), "raw": result}

    msg = result.get("result", {})
    return {
        "ok": True,
        "message_id": msg.get("message_id"),
        "chat_id": msg.get("chat", {}).get("id"),
        "date": msg.get("date"),
    }
