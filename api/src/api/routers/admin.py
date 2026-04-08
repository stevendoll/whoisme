import uuid
from datetime import datetime, timezone

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.api_gateway import Router

import db
from models import Icebreaker, IcebreakerResponse

logger = Logger(service="t12n-api")
router = Router()


@router.get("/admin/icebreakers")
def list_icebreakers():
    response = db.icebreakers_table.scan()
    items = response.get("Items", [])
    result = [IcebreakerResponse(id=i["icebreaker_id"], text=i["text"]).model_dump(by_alias=True) for i in items]
    return {"items": result, "count": len(result)}


@router.post("/admin/icebreakers")
def create_icebreaker():
    body = router.current_event.json_body
    icebreaker_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "icebreaker_id": icebreaker_id,
        "text": body["text"],
        "is_active": body.get("is_active", "true"),
        "created_at": now,
    }
    db.icebreakers_table.put_item(Item=item)
    result = IcebreakerResponse(id=icebreaker_id, text=item["text"])
    return result.model_dump(by_alias=True)


@router.patch("/admin/icebreakers/<icebreaker_id>")
def update_icebreaker(icebreaker_id: str):
    body = router.current_event.json_body
    updates = {}
    expr_names = {}
    expr_values = {}

    if "text" in body:
        updates["#t"] = ":t"
        expr_names["#t"] = "text"
        expr_values[":t"] = body["text"]

    if "is_active" in body:
        updates["#a"] = ":a"
        expr_names["#a"] = "is_active"
        expr_values[":a"] = body["is_active"]

    if not updates:
        return {"error": "No updatable fields provided"}, 400

    set_expr = "SET " + ", ".join(f"{k} = {v}" for k, v in updates.items())
    db.icebreakers_table.update_item(
        Key={"icebreaker_id": icebreaker_id},
        UpdateExpression=set_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )
    return {"updated": icebreaker_id}


@router.delete("/admin/icebreakers/<icebreaker_id>")
def delete_icebreaker(icebreaker_id: str):
    db.icebreakers_table.delete_item(Key={"icebreaker_id": icebreaker_id})
    return {"deleted": icebreaker_id}
