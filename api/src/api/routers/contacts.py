import os
import uuid
from datetime import datetime, timezone

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.api_gateway import Router
from aws_lambda_powertools.event_handler.exceptions import BadRequestError

import db
from models import ContactRequest

logger        = Logger(service="t12n-api")
router        = Router()
_ses          = boto3.client("sesv2", region_name="us-east-1")
_NOTIFY_EMAIL = os.environ.get("NOTIFICATION_EMAIL", "")


def _send_notification(contact_id: str, name: str, email: str, message: str) -> None:
    if not _NOTIFY_EMAIL:
        logger.warning("NOTIFICATION_EMAIL not set — skipping email notification")
        return
    try:
        _ses.send_email(
            FromEmailAddress=_NOTIFY_EMAIL,
            Destination={"ToAddresses": [_NOTIFY_EMAIL]},
            ReplyToAddresses=[email],
            Content={
                "Simple": {
                    "Subject": {"Data": f"t12n.ai contact: {name}"},
                    "Body": {
                        "Text": {
                            "Data": (
                                f"New contact form submission\n\n"
                                f"ID:      {contact_id}\n"
                                f"Name:    {name}\n"
                                f"Email:   {email}\n\n"
                                f"Message:\n{message}\n"
                            )
                        }
                    },
                }
            },
        )
        logger.info(f"Notification email sent for contact {contact_id}")
    except Exception as e:
        logger.error(f"Failed to send notification email: {e}")


@router.post("/contacts")
def create_contact():
    try:
        body = ContactRequest.model_validate(router.current_event.json_body)
    except Exception as e:
        raise BadRequestError(str(e))

    contact_id = str(uuid.uuid4())
    now        = datetime.now(timezone.utc).isoformat()

    db.contacts_table.put_item(Item={
        "contact_id": contact_id,
        "name":       body.name,
        "email":      body.email,
        "message":    body.message,
        "created_at": now,
    })

    logger.info(f"Contact saved: {contact_id} from {body.email}")
    _send_notification(contact_id, body.name, body.email, body.message)
    return {"contactId": contact_id, "createdAt": now}
