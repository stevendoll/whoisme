import json
import boto3
from aws_lambda_powertools import Logger

logger = Logger(service="whoisme-api")

_bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

MODEL_ID = "us.anthropic.claude-3-5-haiku-20241022-v1:0"

def call_bedrock(
    system_prompt: str,
    history: list[dict],
    prefill: str = "{",
    max_tokens: int = 1000,
) -> dict:
    """
    Generic Bedrock call. Returns parsed JSON dict.

    Args:
        system_prompt: System prompt string.
        history: List of {role, content} messages in Bedrock format (must start with user turn).
        prefill: Assistant prefill to force structured output (default: "{").
        max_tokens: Max tokens for the response.

    Retries up to 2 times on parse errors.
    """
    messages_with_prefill = history + [{"role": "assistant", "content": prefill}]

    last_err: Exception = RuntimeError("Unknown error")
    for attempt in range(3):
        try:
            response = _bedrock.invoke_model(
                modelId=MODEL_ID,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": messages_with_prefill,
                }),
            )
            body = json.loads(response["body"].read())
            content = body.get("content", [])
            if not content:
                logger.error(f"Empty Bedrock response: {json.dumps(body)[:500]}")
                raise ValueError(f"Empty content (stop_reason={body.get('stop_reason')!r})")

            raw = prefill + content[0]["text"].strip()
            start = raw.find("{")
            end = raw.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise ValueError(f"No JSON in response: {raw[:200]!r}")

            return json.loads(raw[start:end + 1])

        except (ValueError, KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Bedrock attempt {attempt + 1} failed: {e}")
            last_err = e

    raise last_err
