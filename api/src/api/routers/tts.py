import os
import urllib.request
import json

from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.event_handler.api_gateway import Router
from aws_lambda_powertools.event_handler.exceptions import ServiceError
from aws_lambda_powertools.metrics import MetricUnit

logger   = Logger(service="whoisme-api")
metrics  = Metrics()
router   = Router()

_CARTESIA_TOKEN_URL = "https://api.cartesia.ai/access-token"
_CARTESIA_VERSION   = "2026-08-14"
_TOKEN_TTL_SECONDS  = 60  # only needs to outlive the WebSocket handshake


@router.post("/tts/token")
def create_tts_token():
    """Mint a short-lived, TTS-only Cartesia access token so the API key never reaches the browser."""
    api_key = os.environ.get("CARTESIA_API_KEY", "")
    if not api_key:
        logger.warning("CARTESIA_API_KEY not set — cannot mint TTS token")
        raise ServiceError(503, "TTS unavailable")

    req = urllib.request.Request(
        _CARTESIA_TOKEN_URL,
        data=json.dumps({"grants": {"tts": True}, "expires_in": _TOKEN_TTL_SECONDS}).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Cartesia-Version": _CARTESIA_VERSION,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            token = json.loads(resp.read())["token"]
    except Exception as e:
        logger.error(f"Failed to mint Cartesia access token: {type(e).__name__}")
        metrics.add_metric(name="TtsTokenFailed", unit=MetricUnit.Count, value=1)
        raise ServiceError(502, "TTS token request failed")

    return {"token": token}
