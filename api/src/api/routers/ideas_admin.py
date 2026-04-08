import uuid
from datetime import datetime, timezone

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.api_gateway import Router
from aws_lambda_powertools.event_handler.exceptions import NotFoundError

import db

logger = Logger(service="t12n-api")
router = Router()


@router.get("/admin/ideas")
def list_ideas():
    resp  = db.ideas_table.scan()
    items = resp.get("Items", [])
    items.sort(key=lambda x: x.get("insertion_type", "") + x.get("description", ""))
    return {"items": items, "count": len(items)}


@router.post("/admin/ideas")
def create_idea():
    body      = router.current_event.json_body
    idea_id   = str(uuid.uuid4())
    now       = datetime.now(timezone.utc).isoformat()

    item = {
        "idea_id":        idea_id,
        "text":           body["text"],
        "description":    body.get("description", ""),
        "is_active":      body.get("is_active", True),
        "insertion_type": body.get("insertion_type", "random"),
        "is_once_only":   body.get("is_once_only", False),
        "created_at":     now,
    }
    if body.get("fixed_turn") is not None:
        item["fixed_turn"] = int(body["fixed_turn"])

    db.ideas_table.put_item(Item=item)
    logger.info(f"Idea created: {idea_id}")
    return item


@router.patch("/admin/ideas/<idea_id>")
def update_idea(idea_id: str):
    resp = db.ideas_table.get_item(Key={"idea_id": idea_id})
    if "Item" not in resp:
        raise NotFoundError(f"Idea {idea_id} not found")

    body = router.current_event.json_body
    updates, names, values = [], {}, {}

    for field, expr_name, val_key in [
        ("is_active",      "#ia",   ":ia"),
        ("text",           "#tx",   ":tx"),
        ("description",    "#ds",   ":ds"),
        ("insertion_type", "#it",   ":it"),
        ("fixed_turn",     "#ft",   ":ft"),
        ("is_once_only",   "#io",   ":io"),
    ]:
        if field in body:
            updates.append(f"{expr_name} = {val_key}")
            names[expr_name]  = field
            values[val_key]   = body[field]

    if not updates:
        return resp["Item"]

    db.ideas_table.update_item(
        Key={"idea_id": idea_id},
        UpdateExpression="SET " + ", ".join(updates),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )

    updated = db.ideas_table.get_item(Key={"idea_id": idea_id})
    return updated["Item"]
