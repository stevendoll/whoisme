import os
import uuid
from datetime import datetime, timezone, timedelta

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.api_gateway import Router

import db

logger        = Logger(service="t12n-api")
router        = Router()
_ses          = boto3.client("sesv2", region_name="us-east-1")
_FROM_EMAIL   = os.environ.get("NOTIFICATION_EMAIL", "")
_ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}
_SITE_URL     = os.environ.get("SITE_URL", "https://t12n.ai")
_TOKEN_TTL_S  = 3600  # 1 hour


def _send_magic_link(to_email: str, token: str) -> None:
    link = f"{_SITE_URL}/#/admin?token={token}"
    try:
        _ses.send_email(
            FromEmailAddress=_FROM_EMAIL,
            Destination={"ToAddresses": [to_email]},
            Content={
                "Simple": {
                    "Subject": {"Data": "Your t12n.ai admin link"},
                    "Body": {
                        "Text": {
                            "Data": (
                                f"Click the link below to access the admin panel.\n"
                                f"It expires in 1 hour and can only be used once.\n\n"
                                f"{link}\n"
                            )
                        }
                    },
                }
            },
        )
        logger.info(f"Magic link sent to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send magic link: {e}")


@router.post("/admin/login")
def admin_login():
    body  = router.current_event.json_body
    email = (body.get("email") or "").strip().lower()

    if email in _ADMIN_EMAILS:
        token = str(uuid.uuid4())
        ttl   = int((datetime.now(timezone.utc) + timedelta(seconds=_TOKEN_TTL_S)).timestamp())
        db.admin_tokens_table.put_item(Item={
            "token_id": token,
            "email":    email,
            "ttl":      ttl,
        })
        _send_magic_link(email, token)

    # Always return ok — don't reveal whether email is authorised
    return {"ok": True}


@router.post("/admin/verify")
def admin_verify():
    body  = router.current_event.json_body
    token = (body.get("token") or "").strip()

    if not token:
        return {"ok": False}

    resp = db.admin_tokens_table.get_item(Key={"token_id": token})
    item = resp.get("Item")

    if not item:
        return {"ok": False}

    # Check not expired (belt-and-suspenders; DynamoDB TTL also handles this)
    now = int(datetime.now(timezone.utc).timestamp())
    if item.get("ttl", 0) < now:
        return {"ok": False}

    # One-time use — delete token immediately
    db.admin_tokens_table.delete_item(Key={"token_id": token})
    logger.info(f"Admin verified: {item['email']}")
    return {"ok": True, "email": item["email"]}
