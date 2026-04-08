import os
import urllib.request
import json
from datetime import datetime, timezone

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.api_gateway import Router

logger         = Logger(service="t12n-api")
router         = Router()
_SLACKMAIL_URL = os.environ.get("SLACKMAIL_URL", "")
_SLACKMAIL_KEY = os.environ.get("SLACKMAIL_API_KEY", "")


def _send_slack(message: str) -> None:
    if not _SLACKMAIL_URL or not _SLACKMAIL_KEY:
        logger.warning("SLACKMAIL_URL/API_KEY not set — skipping Slack notification")
        return
    try:
        data = json.dumps({"channel": "dev-tools", "text": message}).encode()
        req = urllib.request.Request(
            f"{_SLACKMAIL_URL}/slack",
            data=data,
            headers={
                "Authorization": f"Bearer {_SLACKMAIL_KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {e}")


@router.post("/errors")
def report_error():
    body       = router.current_event.json_body or {}
    error_type = str(body.get("error_type", "unknown"))
    message    = str(body.get("message", ""))
    now        = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    logger.warning(f"Client error reported — type={error_type} message={message}")

    _send_slack(f"⚠️ TTS failure on t12n.ai\nError: {message}\nTime: {now}")

    return {"ok": True}
