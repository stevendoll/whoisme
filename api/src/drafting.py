"""Shared Bedrock drafting helpers used by interview and users routers."""
import pathlib

from aws_lambda_powertools import Logger
from bedrock_helpers import call_bedrock

logger = Logger(service="whoisme-api")

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"

_DRAFTER_SYSTEM = (_PROMPTS_DIR / "drafter_v1.txt").read_text()

_IDEAS_SUMMARIZER_SYSTEM = """\
You are summarizing a brainstorming conversation into a concise markdown entry for a personal ideas log.

Capture the core idea, key insights surfaced during the conversation, and any concrete next steps or experiments mentioned. Be specific — use the person's own words and examples where possible. Omit filler and pleasantries.

Respond with valid JSON:

{
  "draft": "Markdown content here..."
}

Do not include any text outside the JSON object.
"""


def format_transcript(history: list[dict]) -> str:
    lines = []
    for m in history:
        if m["content"].startswith("[SKIP"):
            continue
        role = "Interviewer" if m["role"] == "assistant" else "User"
        lines.append(f"{role}: {m['content']}")
    return "\n\n".join(lines)


def generate_draft(
    section: str,
    history: list[dict],
    existing_draft: str | None = None,
    feedback: str | None = None,
) -> str:
    """Call Bedrock to draft a profile section. Returns markdown string."""
    transcript = format_transcript(history)

    if feedback and existing_draft:
        user_msg = (
            f"Here is the interview transcript:\n\n{transcript}\n\n"
            f"Here is the current draft of the '{section}' file:\n\n{existing_draft}\n\n"
            f"User feedback: {feedback}\n\n"
            f"Please revise the '{section}' draft incorporating this feedback."
        )
    else:
        user_msg = (
            f"Here is the interview transcript:\n\n{transcript}\n\n"
            f"Please draft the '{section}' file based on this interview."
        )

    result = call_bedrock(
        _DRAFTER_SYSTEM,
        [{"role": "user", "content": user_msg}],
        prefill="{",
        max_tokens=2000,
    )
    return result.get("draft", "")


def summarize_ideas(history: list[dict], today: str) -> str:
    """Summarize an ideas brainstorm conversation into a dated markdown entry."""
    transcript = format_transcript(history)
    user_msg = (
        f"Here is the brainstorming conversation:\n\n{transcript}\n\n"
        f"Please summarize this into a concise ideas log entry."
    )
    result = call_bedrock(
        _IDEAS_SUMMARIZER_SYSTEM,
        [{"role": "user", "content": user_msg}],
        prefill="{",
        max_tokens=1000,
    )
    body = result.get("draft", "").strip()
    return f"## {today}\n{body}\n"
