import json
import pathlib
import boto3
from aws_lambda_powertools import Logger

logger = Logger(service="t12n-api")

_bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

MODEL_ID = "us.anthropic.claude-3-5-haiku-20241022-v1:0"

PROMPT_VERSION = "v1"
SYSTEM_PROMPT = (
    pathlib.Path(__file__).parent / "prompts" / f"consultant_{PROMPT_VERSION}.txt"
).read_text()


def _build_history(conversation_history: list[dict]) -> list[dict]:
    """
    Convert multi-speaker history to Bedrock alternating user/assistant format.
    visitor turns → role: "user"
    consultant turns (both) → role: "assistant", combined as "Alex: ...\nJamie: ..."
    """
    known = {"visitor", "consultant1", "consultant2"}
    items = [x for x in conversation_history if x.get("speaker") in known]
    items.sort(key=lambda x: x["order"])

    messages: list[dict] = []
    i = 0
    while i < len(items):
        item = items[i]
        if item["speaker"] == "visitor":
            messages.append({"role": "user", "content": item["text"]})
            i += 1
        else:
            combined: list[str] = []
            while i < len(items) and items[i]["speaker"] in ("consultant1", "consultant2"):
                name = "Alex" if items[i]["speaker"] == "consultant1" else "Jamie"
                combined.append(f'{name}: {items[i]["text"]}')
                i += 1
            if combined:
                messages.append({"role": "assistant", "content": "\n".join(combined)})

    # Bedrock requires conversation to start with a user turn
    while messages and messages[0]["role"] != "user":
        messages.pop(0)

    logger.info(f"Bedrock history: {len(messages)} messages")
    return messages


def _cap_words(text: str, limit: int = 30) -> str:
    """Hard-cap a response at `limit` words, ending on the last sentence boundary if possible."""
    words = text.split()
    if len(words) <= limit:
        return text
    truncated = " ".join(words[:limit])
    for punct in (".", "!", "?"):
        idx = truncated.rfind(punct)
        if idx > len(truncated) // 2:
            return truncated[: idx + 1]
    return truncated + "."


def _invoke_bedrock(messages: list[dict], system: str) -> dict[str, str]:
    """Single Bedrock call. Uses assistant prefill '{' to force JSON output."""
    messages_with_prefill = messages + [{"role": "assistant", "content": "{"}]

    response = _bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "system": system,
            "messages": messages_with_prefill,
        }),
    )
    body    = json.loads(response["body"].read())
    content = body.get("content", [])
    if not content:
        logger.error(f"Empty Bedrock response: {json.dumps(body)[:500]}")
        raise ValueError(f"Empty content (stop_reason={body.get('stop_reason')!r})")

    raw   = "{" + content[0]["text"].strip()
    start = raw.find("{")
    end   = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No JSON in response: {raw[:200]!r}")

    parsed = json.loads(raw[start : end + 1])
    c1 = str(parsed.get("consultant1", "")).strip()
    c2 = str(parsed.get("consultant2", "")).strip()
    if not c1 or not c2:
        raise ValueError(f"Missing consultant key(s): {list(parsed.keys())}")
    return {"consultant1": _cap_words(c1), "consultant2": _cap_words(c2)}


def generate_consultant_replies(
    conversation_history: list[dict],
    nudge: str | None = None,
) -> dict[str, str]:
    """
    Call Bedrock and return {"consultant1": "...", "consultant2": "..."}.
    nudge: optional topic/idea to weave in organically.
    Retries up to 2 times on parse errors.
    """
    messages = _build_history(conversation_history)
    system   = SYSTEM_PROMPT

    if nudge:
        system += (
            '\n\nNUDGE: Organically weave in the following topic — don\'t announce it, '
            f'let it surface naturally in one of the replies: "{nudge}"'
        )

    logger.info(f"Bedrock call prompt_version={PROMPT_VERSION}")
    last_err: Exception = RuntimeError("Unknown error")
    for attempt in range(3):
        try:
            return _invoke_bedrock(messages, system)
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Bedrock attempt {attempt + 1} failed: {e}")
            last_err = e

    raise last_err
