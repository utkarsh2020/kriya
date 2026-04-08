"""
AgentOS skill – Slack
Posts messages and reads channel history via the Slack Web API.
Pure stdlib: urllib.request only. No external dependencies.

Secrets (set via: agent secret set --project <p> --key <K>):
  SLACK_TOKEN           — Bot User OAuth Token (xoxb-...)
  SLACK_DEFAULT_CHANNEL — Default channel (#general or channel ID, optional)
"""
import json
import urllib.request
import urllib.error

SKILL_ID = "slack.post"
SKILL_VERSION = "1.0.0"

_API = "https://slack.com/api/{method}"


def _call(token: str, method: str, payload: dict) -> dict:
    url  = _API.format(method=method)
    body = json.dumps(payload).encode()
    req  = urllib.request.Request(
        url, data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
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
    Post a message to Slack or read channel history.

    params:
      action  : "post" (default) | "history" | "channels"
      channel : Channel name or ID (required for post/history; falls back to SLACK_DEFAULT_CHANNEL)
      text    : Message text (required for post)
      blocks  : Slack Block Kit JSON list (optional, overrides text for rich layout)
      limit   : Max messages for history (default 10, max 200)
      cursor  : Pagination cursor for history

    secrets:
      SLACK_TOKEN           — required
      SLACK_DEFAULT_CHANNEL — default channel (used when channel not in params)
    """
    token = secrets.get("SLACK_TOKEN", "").strip()
    if not token:
        return {"error": "SLACK_TOKEN secret not set"}

    action = params.get("action", "post")

    if action == "channels":
        result = _call(token, "conversations.list", {"limit": 200, "types": "public_channel,private_channel"})
        if not result.get("ok"):
            return {"error": result.get("error", "Slack API error")}
        channels = [
            {"id": c["id"], "name": c["name"], "is_private": c.get("is_private", False)}
            for c in result.get("channels", [])
        ]
        return {"ok": True, "channels": channels}

    channel = params.get("channel") or secrets.get("SLACK_DEFAULT_CHANNEL", "").strip()
    if not channel:
        return {"error": "channel required (pass in params or set SLACK_DEFAULT_CHANNEL secret)"}

    if action == "history":
        payload: dict = {
            "channel": channel,
            "limit": min(int(params.get("limit", 10)), 200),
        }
        if "cursor" in params:
            payload["cursor"] = params["cursor"]
        result = _call(token, "conversations.history", payload)
        if not result.get("ok"):
            return {"error": result.get("error", "Slack API error")}
        messages = [
            {"ts": m["ts"], "user": m.get("user"), "text": m.get("text", "")}
            for m in result.get("messages", [])
        ]
        return {"ok": True, "messages": messages, "count": len(messages),
                "has_more": result.get("has_more", False)}

    # Default: post message
    text = params.get("text", "").strip()
    blocks = params.get("blocks")
    if not text and not blocks:
        return {"error": "text (or blocks) required for post action"}

    payload = {"channel": channel}
    if blocks:
        payload["blocks"] = blocks
        payload["text"] = text or "(no fallback text)"
    else:
        payload["text"] = text

    result = _call(token, "chat.postMessage", payload)
    if not result.get("ok"):
        return {"error": result.get("error", "Slack API error")}

    return {
        "ok": True,
        "ts": result.get("ts"),
        "channel": result.get("channel"),
        "message_text": result.get("message", {}).get("text"),
    }
