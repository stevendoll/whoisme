import random
from datetime import datetime, timezone

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.api_gateway import Router
from aws_lambda_powertools.event_handler.exceptions import NotFoundError
from boto3.dynamodb.conditions import Key

import db
from models import Icebreaker, IcebreakerResponse

logger = Logger(service="t12n-api")
router = Router()


@router.get("/conversations/icebreakers")
def get_icebreaker():
    response = db.icebreakers_table.query(
        IndexName="is_active-index",
        KeyConditionExpression=Key("is_active").eq("true"),
    )
    items = response.get("Items", [])
    if not items:
        raise NotFoundError("No active icebreakers found")

    item = random.choice(items)
    icebreaker = Icebreaker(**item)
    result = IcebreakerResponse(id=icebreaker.icebreaker_id, text=icebreaker.text)
    return result.model_dump(by_alias=True)
