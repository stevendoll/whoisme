import re
import random
from datetime import datetime, timezone

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.api_gateway import Router
from boto3.dynamodb.conditions import Key, Attr

import db
from bedrock_helpers import generate_consultant_replies
from models import TurnRequest, Turn, ConsultantReply, TurnResponse


def _extract_emotion(text: str) -> tuple[str, str | None]:
    """Strip leading <emotion:X> tag and return (clean_text, emotion_name)."""
    m = re.match(r'<emotion:(\w+)>\s*', text)
    if m:
        return text[m.end():].strip(), m.group(1)
    return text, None

logger = Logger(service="t12n-api")
router = Router()


# ── Reply sequence weights ────────────────────────────────────────────────────
# First reply always: c1 → c2
# Subsequent replies (weighted random):
#   60%  consultant1 → consultant2
#   10%  consultant2 → consultant1
#   10%  consultant1 only
#   10%  consultant2 only
#   10%  consultant1 → consultant2 → consultant2 (follow-up)

def _pick_reply_sequence(is_first_reply: bool) -> list[str]:
    if is_first_reply:
        return ["consultant1", "consultant2"]
    r = random.random()
    if r < 0.60: return ["consultant1", "consultant2"]
    elif r < 0.70: return ["consultant2", "consultant1"]
    elif r < 0.80: return ["consultant1"]
    elif r < 0.90: return ["consultant2"]
    else:          return ["consultant1", "consultant2", "consultant2"]


# ── Idea injection ────────────────────────────────────────────────────────────

def _load_active_ideas() -> list[dict]:
    try:
        resp = db.ideas_table.scan(FilterExpression=Attr("is_active").eq(True))
        return resp.get("Items", [])
    except Exception as e:
        logger.warning(f"Failed to load ideas: {e}")
        return []


def _pick_idea(visitor_turn_count: int, used_ideas: list[str]) -> dict | None:
    ideas = _load_active_ideas()
    if not ideas:
        return None

    # Fixed ideas fire at a specific visitor turn number
    for idea in ideas:
        if idea.get("insertion_type") == "fixed":
            fixed_turn = idea.get("fixed_turn")
            if fixed_turn is not None and int(fixed_turn) == visitor_turn_count:
                if idea.get("is_once_only") and idea["idea_id"] in used_ideas:
                    continue
                return idea

    # Random ideas fire with 25% probability per turn
    if random.random() < 0.25:
        candidates = [
            i for i in ideas
            if i.get("insertion_type") == "random"
            and i["idea_id"] not in used_ideas
        ]
        if candidates:
            return random.choice(candidates)

    return None


# ── Conversation record helpers ───────────────────────────────────────────────

def _get_conversation(conversation_id: str) -> dict:
    resp = db.conversations_table.get_item(Key={"conversation_id": conversation_id})
    return resp.get("Item", {})


def _create_conversation(conversation_id: str, preview: str, voices: dict, now: str) -> None:
    try:
        db.conversations_table.put_item(
            Item={
                "conversation_id": conversation_id,
                "created_at": now,
                "preview": preview[:120],
                "voices": voices,
                "used_ideas": [],
            },
            ConditionExpression="attribute_not_exists(conversation_id)",
        )
    except db.conversations_table.meta.client.exceptions.ConditionalCheckFailedException:
        pass  # already exists — idempotent


def _mark_idea_used(conversation_id: str, idea_id: str) -> None:
    try:
        db.conversations_table.update_item(
            Key={"conversation_id": conversation_id},
            UpdateExpression="SET used_ideas = list_append(if_not_exists(used_ideas, :empty), :new_id)",
            ExpressionAttributeValues={":empty": [], ":new_id": [idea_id]},
        )
    except Exception as e:
        logger.warning(f"Failed to mark idea used: {e}")


# ── Route ─────────────────────────────────────────────────────────────────────

@router.post("/conversations/<conversation_id>/turns")
def post_turn(conversation_id: str):
    body   = TurnRequest.model_validate(router.current_event.json_body)
    now    = datetime.now(timezone.utc).isoformat()
    voices = body.voices or {}

    # ── Save the incoming turn ────────────────────────────────────────────────
    turn_item: dict = {
        "conversation_id": conversation_id,
        "order":           body.order,
        "text":            body.text,
        "speaker":         body.speaker,
        "created_at":      now,
    }
    voice_id = voices.get(body.speaker)
    if voice_id:
        turn_item["voice_id"] = voice_id

    try:
        db.turns_table.put_item(
            Item=turn_item,
            ConditionExpression="attribute_not_exists(conversation_id) AND attribute_not_exists(#o)",
            ExpressionAttributeNames={"#o": "order"},
        )
    except db.turns_table.meta.client.exceptions.ConditionalCheckFailedException:
        pass  # idempotent

    saved_turn = Turn(
        conversation_id=conversation_id,
        order=body.order,
        text=body.text,
        speaker=body.speaker,
        voice_id=voice_id or None,
        created_at=now,
    )

    # Non-visitor turns don't trigger consultant replies
    if body.speaker != "visitor":
        return TurnResponse(turn=saved_turn).model_dump(by_alias=True)

    # ── Fetch full history ────────────────────────────────────────────────────
    history_resp = db.turns_table.query(
        KeyConditionExpression=Key("conversation_id").eq(conversation_id),
    )
    history = sorted(history_resp.get("Items", []), key=lambda x: x["order"])

    visitor_turn_count = sum(1 for t in history if t.get("speaker") == "visitor")
    is_first_reply     = visitor_turn_count == 1

    # ── Upsert conversation record (on first visitor turn) ───────────────────
    if is_first_reply:
        _create_conversation(conversation_id, body.text, voices, now)

    # ── Pick idea to inject ───────────────────────────────────────────────────
    conversation = _get_conversation(conversation_id)
    used_ideas   = list(conversation.get("used_ideas", []))
    idea         = _pick_idea(visitor_turn_count, used_ideas)
    nudge        = idea["text"] if idea else None

    # ── Generate Bedrock replies ──────────────────────────────────────────────
    replies = generate_consultant_replies(history, nudge=nudge)

    # ── Determine reply sequence ──────────────────────────────────────────────
    sequence = _pick_reply_sequence(is_first_reply)

    # For the 3-reply variant, generate a follow-up from consultant2
    followup_text: str | None = None
    if len(sequence) == 3:
        followup_history = history + [
            {"speaker": "consultant1", "order": body.order + 1, "text": replies["consultant1"]},
            {"speaker": "consultant2", "order": body.order + 2, "text": replies["consultant2"]},
        ]
        try:
            followup = generate_consultant_replies(followup_history)
            followup_text = followup["consultant2"]
        except Exception as e:
            logger.warning(f"Follow-up Bedrock call failed, dropping third reply: {e}")
            sequence = ["consultant1", "consultant2"]

    # ── Save and build consultant replies ─────────────────────────────────────
    ai_now             = datetime.now(timezone.utc).isoformat()
    consultant_replies: list[ConsultantReply] = []
    idea_stamped       = False

    for idx, speaker_key in enumerate(sequence):
        if speaker_key == "consultant2" and idx == 2 and followup_text:
            raw_text = followup_text
        else:
            raw_text = replies[speaker_key]

        text, emotion    = _extract_emotion(raw_text)
        reply_order      = body.order + idx + 1
        reply_voice_id   = voices.get(speaker_key)

        item: dict = {
            "conversation_id": conversation_id,
            "order":           reply_order,
            "text":            text,
            "speaker":         speaker_key,
            "created_at":      ai_now,
        }
        if reply_voice_id:
            item["voice_id"] = reply_voice_id
        # Stamp idea_id on the first consultant reply where it was used
        if idea and not idea_stamped:
            item["idea_id"] = idea["idea_id"]
            idea_stamped = True

        try:
            db.turns_table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(conversation_id) AND attribute_not_exists(#o)",
                ExpressionAttributeNames={"#o": "order"},
            )
        except db.turns_table.meta.client.exceptions.ConditionalCheckFailedException:
            pass

        consultant_replies.append(ConsultantReply(
            order=reply_order,
            text=text,
            speaker=speaker_key,  # type: ignore[arg-type]
            voice_id=reply_voice_id or None,
            emotion=emotion,
        ))

    # ── Record once-only idea as used ─────────────────────────────────────────
    if idea and idea.get("is_once_only"):
        _mark_idea_used(conversation_id, idea["idea_id"])

    return TurnResponse(turn=saved_turn, consultant_replies=consultant_replies).model_dump(by_alias=True)
