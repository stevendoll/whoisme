import pathlib
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.api_gateway import Router
from aws_lambda_powertools.event_handler.exceptions import BadRequestError, NotFoundError

import db
from bedrock_helpers import call_bedrock
from drafting import generate_draft
from models import SECTIONS, CONTEXT_SECTIONS

logger = Logger(service="whoisme-api")
router = Router()

_PROMPTS_DIR = pathlib.Path(__file__).parent.parent.parent / "prompts"

_INTERVIEWER_SYSTEM = (_PROMPTS_DIR / "interviewer_v1.txt").read_text()

# Ideas collaborator prompt loaded at startup; other context prompts loaded on demand
_IDEAS_SYSTEM = (_PROMPTS_DIR / "ideas_v1.txt").read_text()

_SESSION_TTL_DAYS = 30
_DEFAULT_QUESTIONS = 20

# Profile-only sections (exclude context sections from draft generation)
_PROFILE_SECTIONS = [s for s in SECTIONS if s not in CONTEXT_SECTIONS]


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


def _call_interviewer(session: dict, force_heckle: bool = False) -> dict:
    """Ask Bedrock for the next interview question. Returns parsed JSON dict."""
    history = list(session.get("history", []))

    if not history:
        history = [{"role": "user", "content": "Please begin the interview."}]

    skipped = session.get("skipped_sections", [])
    system = _INTERVIEWER_SYSTEM
    if skipped:
        system += f"\n\nDo not ask questions about these sections (user has skipped them): {', '.join(skipped)}."
    if force_heckle:
        system += "\n\nforce_heckle: true — you MUST include a heckle in this response."

    return call_bedrock(system, history, prefill="{", max_tokens=600)


def _call_ideas_collaborator(session: dict) -> dict:
    """Ask Bedrock for the next ideas collaborator message. Returns parsed JSON dict."""
    history = list(session.get("history", []))
    if not history:
        history = [{"role": "user", "content": "Please begin."}]
    return call_bedrock(_IDEAS_SYSTEM, history, prefill="{", max_tokens=400)


def _enter_review(session: dict) -> dict:
    """Generate drafts for all non-skipped profile sections concurrently and flip phase to reviewing."""
    skipped = set(session.get("skipped_sections", []))
    history = session.get("history", [])

    draft_files = dict(session.get("draft_files", {}))
    # Only draft profile sections, never context sections
    sections_to_draft = [s for s in _PROFILE_SECTIONS if s not in skipped and s not in draft_files]

    def _draft_one(section: str) -> tuple[str, str]:
        return section, generate_draft(section, history)

    with ThreadPoolExecutor(max_workers=len(sections_to_draft) or 1) as pool:
        futures = {pool.submit(_draft_one, s): s for s in sections_to_draft}
        for future in as_completed(futures):
            section = futures[future]
            try:
                _, draft = future.result()
                draft_files[section] = draft
            except Exception as e:
                logger.error(f"Draft generation failed for section '{section}': {e}")
                draft_files[section] = ""

    session["phase"] = "reviewing"
    session["draft_files"] = draft_files
    return session


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/interview")
def create_session():
    body = router.current_event.json_body or {}
    context_type = (body.get("context_type") or "").strip() or None

    if context_type and context_type not in CONTEXT_SECTIONS:
        raise BadRequestError(f"Unknown context_type: {context_type}. Must be one of: {list(CONTEXT_SECTIONS.keys())}")

    session_id = str(uuid.uuid4())
    session = {
        "session_id": session_id,
        "user_id": None,
        "history": [],
        "phase": "interviewing",
        "questions_asked": 0,
        "section_density": {s: 0 for s in _PROFILE_SECTIONS},
        "skipped_sections": [],
        "approved_files": {},
        "draft_files": {},
        "created_at": _now_iso(),
        "ttl": _ttl_ts(),
    }

    if context_type:
        section_def = CONTEXT_SECTIONS[context_type]
        session["context_type"] = context_type

        if section_def.questions:
            # Hardcoded questions — no Bedrock
            first_question = section_def.questions[0]
            questions_total = len(section_def.questions)
            heckle = None
        else:
            # AI-driven (ideas)
            result = _call_ideas_collaborator(session)
            first_question = result.get("message", "What's on your mind?")
            questions_total = section_def.ai_questions_count
            heckle = None

        session["questions_total"] = questions_total
        session["history"] = [
            {"role": "user", "content": "Please begin."},
            {"role": "assistant", "content": first_question},
        ]
        _save_session(session)

        return {
            "session_id": session_id,
            "message": first_question,
            "heckle": heckle,
            "questions_remaining": questions_total,
            "questions_total": questions_total,
        }

    # Standard interview flow
    session["questions_total"] = _DEFAULT_QUESTIONS
    result = _call_interviewer(session)
    first_question = result.get("message", "")
    heckle = result.get("heckle")

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

    context_type = session.get("context_type")
    history = list(session.get("history", []))
    history.append({"role": "user", "content": text})

    questions_asked = int(session.get("questions_asked", 0)) + 1
    questions_total = int(session.get("questions_total", _DEFAULT_QUESTIONS))
    questions_remaining = questions_total - questions_asked

    session["history"] = history
    session["questions_asked"] = questions_asked

    if context_type:
        section_def = CONTEXT_SECTIONS[context_type]

        if questions_remaining <= 0:
            # All questions answered — mark complete without drafting
            session["phase"] = "complete"
            _save_session(session)
            return {
                "message": "Got it — I have everything I need.",
                "sections_touched": [context_type],
                "heckle": None,
                "questions_remaining": 0,
                "phase": "complete",
                "draft_files": None,
            }

        if section_def.questions:
            # Return next hardcoded question
            next_question = section_def.questions[questions_asked]
            message = next_question
            heckle = None
        else:
            # AI-driven (ideas): call Bedrock for next question
            result = _call_ideas_collaborator(session)
            message = result.get("message", "")
            heckle = None

        history.append({"role": "assistant", "content": message})
        session["history"] = history
        _save_session(session)

        return {
            "message": message,
            "sections_touched": [context_type],
            "heckle": heckle,
            "questions_remaining": max(0, questions_remaining),
            "phase": "interviewing",
            "draft_files": None,
        }

    # Standard interview flow
    result = _call_interviewer(session, force_heckle=(questions_asked == 2))

    message = result.get("message", "")
    sections_touched = result.get("sections_touched", [])
    heckle = result.get("heckle")

    density = dict(session.get("section_density", {}))
    for s in sections_touched:
        if s in density:
            density[s] = density[s] + 1
        elif s in SECTIONS:
            density[s] = 1
    session["section_density"] = density

    history.append({"role": "assistant", "content": message})
    session["history"] = history

    if questions_remaining <= 0:
        session = _enter_review(session)

    _save_session(session)

    return {
        "message": message,
        "sections_touched": sections_touched,
        "heckle": heckle,
        "questions_remaining": max(0, questions_remaining),
        "phase": session["phase"],
        "draft_files": session.get("draft_files") if session["phase"] == "reviewing" else None,
    }


@router.post("/interview/<session_id>/context-end")
def context_end(session_id: str):
    """End a context session early (e.g. user clicks 'Done brainstorming')."""
    session = _get_session(session_id)
    context_type = session.get("context_type")
    if not context_type:
        raise BadRequestError("Not a context session")
    if session["phase"] == "complete":
        return {"ok": True}
    if session["phase"] != "interviewing":
        raise BadRequestError(f"Session is in '{session['phase']}' phase")

    session["phase"] = "complete"
    _save_session(session)
    return {"ok": True}


@router.post("/interview/<session_id>/skip-question")
def skip_question(session_id: str):
    session = _get_session(session_id)
    if session["phase"] != "interviewing":
        raise BadRequestError(f"Session is in '{session['phase']}' phase")

    history = list(session.get("history", []))
    history.append({"role": "user", "content": "[SKIP: Please ask a different question on a different topic]"})
    session["history"] = history

    result = _call_interviewer(session, force_heckle=True)
    new_question = result.get("message", "")
    heckle = result.get("heckle")

    history.append({"role": "assistant", "content": new_question})
    session["history"] = history
    _save_session(session)

    questions_remaining = int(session.get("questions_total", _DEFAULT_QUESTIONS)) - int(session.get("questions_asked", 0))
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

    result = _call_interviewer(session, force_heckle=True)
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
    if session.get("context_type"):
        raise BadRequestError("Use /context-end for context sessions")
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
    count = int(body.get("count") if body.get("count") is not None else 10)
    if count < 1 or count > 50:
        raise BadRequestError("count must be between 1 and 50")

    session = _get_session(session_id)
    if session["phase"] != "reviewing":
        raise BadRequestError("Session is not in reviewing phase")

    session["questions_total"] = session.get("questions_total", _DEFAULT_QUESTIONS) + count
    session["phase"] = "interviewing"
    session["draft_files"] = {}

    result = _call_interviewer(session)
    new_question = result.get("message", "")
    heckle = result.get("heckle")

    history = list(session.get("history", []))
    history.append({"role": "assistant", "content": new_question})
    session["history"] = history
    _save_session(session)

    questions_remaining = int(session["questions_total"]) - int(session.get("questions_asked", 0))
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
    approved_files_at = dict(session.get("approved_files_at", {}))
    approved_files_at[file] = _now_iso()
    session["approved_files"] = approved_files
    session["approved_files_at"] = approved_files_at
    _save_session(session)

    return {"approved_files": list(approved_files.keys()), "approved_files_at": approved_files_at}


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
    new_draft = generate_draft(file, session.get("history", []), existing_draft, feedback_text)

    draft_files[file] = new_draft
    session["draft_files"] = draft_files
    _save_session(session)

    return {"file": file, "draft": new_draft}


@router.get("/interview/<session_id>")
def get_session(session_id: str):
    session = _get_session(session_id)
    q_total = int(session.get("questions_total", _DEFAULT_QUESTIONS))
    q_asked = int(session.get("questions_asked", 0))
    return {
        "session_id": session["session_id"],
        "phase": session.get("phase", "interviewing"),
        "questions_asked": q_asked,
        "questions_total": q_total,
        "questions_remaining": max(0, q_total - q_asked),
        "section_density": session.get("section_density", {}),
        "skipped_sections": session.get("skipped_sections", []),
        "approved_files": list(session.get("approved_files", {}).keys()),
        "draft_files": list(session.get("draft_files", {}).keys()),
        "context_type": session.get("context_type"),
    }
