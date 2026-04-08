import pathlib
import uuid
from datetime import datetime, timezone, timedelta

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.api_gateway import Router
from aws_lambda_powertools.event_handler.exceptions import BadRequestError, NotFoundError

import db
from bedrock_helpers import call_bedrock
from models import SECTIONS

logger = Logger(service="whoisme-api")
router = Router()

_INTERVIEWER_SYSTEM = (
    pathlib.Path(__file__).parent.parent.parent / "prompts" / "interviewer_v1.txt"
).read_text()

_DRAFTER_SYSTEM = (
    pathlib.Path(__file__).parent.parent.parent / "prompts" / "drafter_v1.txt"
).read_text()

_SESSION_TTL_DAYS = 30
_DEFAULT_QUESTIONS = 20


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ttl_ts(days: int = _SESSION_TTL_DAYS) -> int:
    return int((datetime.now(timezone.utc) + timedelta(days=days)).timestamp())


def _get_session(session_id: str) -> dict:
    resp = db.interview_sessions_table.get_item(Key={"session_id": session_id})
    item = resp.get("Item")
    if not item:
        raise NotFoundError("Session not found")
    return item


def _save_session(session: dict) -> None:
    db.interview_sessions_table.put_item(Item=session)


def _call_interviewer(session: dict) -> dict:
    """Ask Bedrock for the next interview question. Returns parsed JSON dict."""
    history = list(session.get("history", []))

    # Bedrock requires conversation to start with a user turn
    if not history:
        history = [{"role": "user", "content": "Please begin the interview."}]

    skipped = session.get("skipped_sections", [])
    system = _INTERVIEWER_SYSTEM
    if skipped:
        system += f"\n\nDo not ask questions about these sections (user has skipped them): {', '.join(skipped)}."

    return call_bedrock(system, history, prefill="{", max_tokens=600)


def _format_transcript(history: list[dict]) -> str:
    lines = []
    for m in history:
        if m["content"].startswith("[SKIP"):
            continue
        role = "Interviewer" if m["role"] == "assistant" else "User"
        lines.append(f"{role}: {m['content']}")
    return "\n\n".join(lines)


def _generate_draft(section: str, history: list[dict], existing_draft: str | None = None, feedback: str | None = None) -> str:
    """Call Bedrock to draft a single section. Returns markdown string."""
    transcript = _format_transcript(history)

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


def _enter_review(session: dict) -> dict:
    """Generate drafts for all non-skipped sections and flip phase to reviewing."""
    skipped = set(session.get("skipped_sections", []))
    history = session.get("history", [])

    draft_files = dict(session.get("draft_files", {}))
    for section in SECTIONS:
        if section not in skipped and section not in draft_files:
            draft_files[section] = _generate_draft(section, history)

    session["phase"] = "reviewing"
    session["draft_files"] = draft_files
    return session


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/interview")
def create_session():
    session_id = str(uuid.uuid4())
    session = {
        "session_id": session_id,
        "user_id": None,
        "history": [],
        "phase": "interviewing",
        "questions_asked": 0,
        "questions_total": _DEFAULT_QUESTIONS,
        "section_density": {s: 0 for s in SECTIONS},
        "skipped_sections": [],
        "approved_files": {},
        "draft_files": {},
        "created_at": _now_iso(),
        "ttl": _ttl_ts(),
    }

    result = _call_interviewer(session)
    first_question = result.get("message", "")
    heckle = result.get("heckle")

    # Store first question as assistant turn; no user turn yet
    session["history"] = [
        {"role": "user", "content": "Please begin the interview."},
        {"role": "assistant", "content": first_question},
    ]
    _save_session(session)

    return {
        "session_id": session_id,
        "message": first_question,
        "heckle": heckle,
        "questions_remaining": _DEFAULT_QUESTIONS,
        "questions_total": _DEFAULT_QUESTIONS,
    }


@router.post("/interview/<session_id>/respond")
def respond(session_id: str):
    body = router.current_event.json_body or {}
    text = (body.get("text") or "").strip()
    if not text:
        raise BadRequestError("text is required")

    session = _get_session(session_id)
    if session["phase"] != "interviewing":
        raise BadRequestError(f"Session is in '{session['phase']}' phase")

    # Append user answer to history
    history = list(session.get("history", []))
    history.append({"role": "user", "content": text})

    # Ask Bedrock for next question (with full history including this answer)
    session["history"] = history
    result = _call_interviewer(session)

    message = result.get("message", "")
    sections_touched = result.get("sections_touched", [])
    heckle = result.get("heckle")

    # Update section density
    density = dict(session.get("section_density", {}))
    for s in sections_touched:
        if s in density:
            density[s] = density[s] + 1
        elif s in SECTIONS:
            density[s] = 1
    session["section_density"] = density

    questions_asked = session.get("questions_asked", 0) + 1
    questions_total = session.get("questions_total", _DEFAULT_QUESTIONS)
    questions_remaining = questions_total - questions_asked

    # Append interviewer question to history
    history.append({"role": "assistant", "content": message})
    session["history"] = history
    session["questions_asked"] = questions_asked

    if questions_remaining <= 0:
        session = _enter_review(session)

    _save_session(session)

    return {
        "message": message,
        "sections_touched": sections_touched,
        "heckle": heckle,
        "questions_remaining": max(0, questions_remaining),
        "phase": session["phase"],
    }


@router.post("/interview/<session_id>/skip-question")
def skip_question(session_id: str):
    session = _get_session(session_id)
    if session["phase"] != "interviewing":
        raise BadRequestError(f"Session is in '{session['phase']}' phase")

    # Add skip marker to history so the LLM knows this was skipped
    history = list(session.get("history", []))
    history.append({"role": "user", "content": "[SKIP: Please ask a different question on a different topic]"})
    session["history"] = history

    result = _call_interviewer(session)
    new_question = result.get("message", "")
    heckle = result.get("heckle")

    history.append({"role": "assistant", "content": new_question})
    session["history"] = history
    _save_session(session)

    questions_remaining = session.get("questions_total", _DEFAULT_QUESTIONS) - session.get("questions_asked", 0)
    return {
        "message": new_question,
        "heckle": heckle,
        "questions_remaining": max(0, questions_remaining),
    }


@router.post("/interview/<session_id>/skip-section")
def skip_section(session_id: str):
    body = router.current_event.json_body or {}
    section = (body.get("section") or "").strip()
    if section not in SECTIONS:
        raise BadRequestError(f"Unknown section: {section}")

    session = _get_session(session_id)
    skipped = list(session.get("skipped_sections", []))
    if section not in skipped:
        skipped.append(section)
    session["skipped_sections"] = skipped

    # Get a new question avoiding skipped sections
    result = _call_interviewer(session)
    new_question = result.get("message", "")
    heckle = result.get("heckle")

    history = list(session.get("history", []))
    history.append({"role": "user", "content": f"[SKIP SECTION: {section}]"})
    history.append({"role": "assistant", "content": new_question})
    session["history"] = history
    _save_session(session)

    return {"message": new_question, "heckle": heckle, "skipped_sections": skipped}


@router.post("/interview/<session_id>/reactivate-section")
def reactivate_section(session_id: str):
    body = router.current_event.json_body or {}
    section = (body.get("section") or "").strip()
    if section not in SECTIONS:
        raise BadRequestError(f"Unknown section: {section}")

    session = _get_session(session_id)
    skipped = [s for s in session.get("skipped_sections", []) if s != section]
    session["skipped_sections"] = skipped
    _save_session(session)

    return {"skipped_sections": skipped}


@router.post("/interview/<session_id>/pause")
def pause_session(session_id: str):
    session = _get_session(session_id)
    if session["phase"] != "interviewing":
        raise BadRequestError(f"Session is already in '{session['phase']}' phase")

    session = _enter_review(session)
    _save_session(session)

    return {
        "phase": "reviewing",
        "draft_files": session.get("draft_files", {}),
        "skipped_sections": session.get("skipped_sections", []),
    }


@router.post("/interview/<session_id>/more")
def more_questions(session_id: str):
    body = router.current_event.json_body or {}
    count = int(body.get("count") or 10)
    if count < 1 or count > 50:
        raise BadRequestError("count must be between 1 and 50")

    session = _get_session(session_id)
    if session["phase"] != "reviewing":
        raise BadRequestError("Session is not in reviewing phase")

    session["questions_total"] = session.get("questions_total", _DEFAULT_QUESTIONS) + count
    session["phase"] = "interviewing"
    # Clear draft_files so review phase regenerates fresh drafts next time
    session["draft_files"] = {}

    result = _call_interviewer(session)
    new_question = result.get("message", "")
    heckle = result.get("heckle")

    history = list(session.get("history", []))
    history.append({"role": "assistant", "content": new_question})
    session["history"] = history
    _save_session(session)

    questions_remaining = session["questions_total"] - session.get("questions_asked", 0)
    return {
        "message": new_question,
        "heckle": heckle,
        "questions_remaining": max(0, questions_remaining),
        "phase": "interviewing",
    }


@router.post("/interview/<session_id>/review/approve")
def review_approve(session_id: str):
    body = router.current_event.json_body or {}
    file = (body.get("file") or "").strip()
    if file not in SECTIONS:
        raise BadRequestError(f"Unknown section: {file}")

    session = _get_session(session_id)
    if session["phase"] != "reviewing":
        raise BadRequestError("Session is not in reviewing phase")

    draft_files = dict(session.get("draft_files", {}))
    approved_files = dict(session.get("approved_files", {}))

    draft = draft_files.get(file, "")
    if not draft:
        raise BadRequestError(f"No draft exists for section: {file}")

    approved_files[file] = draft
    session["approved_files"] = approved_files
    _save_session(session)

    return {"approved_files": list(approved_files.keys())}


@router.post("/interview/<session_id>/review/feedback")
def review_feedback(session_id: str):
    body = router.current_event.json_body or {}
    file = (body.get("file") or "").strip()
    feedback_text = (body.get("text") or "").strip()
    if file not in SECTIONS:
        raise BadRequestError(f"Unknown section: {file}")
    if not feedback_text:
        raise BadRequestError("text is required")

    session = _get_session(session_id)
    if session["phase"] != "reviewing":
        raise BadRequestError("Session is not in reviewing phase")

    draft_files = dict(session.get("draft_files", {}))
    existing_draft = draft_files.get(file, "")
    new_draft = _generate_draft(file, session.get("history", []), existing_draft, feedback_text)

    draft_files[file] = new_draft
    session["draft_files"] = draft_files
    _save_session(session)

    return {"file": file, "draft": new_draft}


@router.get("/interview/<session_id>")
def get_session(session_id: str):
    session = _get_session(session_id)
    return {
        "session_id": session["session_id"],
        "phase": session.get("phase", "interviewing"),
        "questions_asked": session.get("questions_asked", 0),
        "questions_total": session.get("questions_total", _DEFAULT_QUESTIONS),
        "questions_remaining": max(0, session.get("questions_total", _DEFAULT_QUESTIONS) - session.get("questions_asked", 0)),
        "section_density": session.get("section_density", {}),
        "skipped_sections": session.get("skipped_sections", []),
        "approved_files": list(session.get("approved_files", {}).keys()),
        "draft_files": list(session.get("draft_files", {}).keys()),
    }
