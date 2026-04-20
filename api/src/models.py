from dataclasses import dataclass
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from typing import Literal, Optional


# ── Context section registry ──────────────────────────────────────────────────

@dataclass
class ContextSectionDef:
    key: str
    label: str
    default_visibility: str           # "public" | "private"
    questions: list[str]              # hardcoded questions; empty = AI-driven
    format_template: Optional[str]    # template with {date}, {q0}, {q1}…; None = AI formats
    ai_prompt_file: Optional[str]     # prompt filename for AI-driven sessions
    ai_questions_count: int = 6       # turns for AI-driven sessions


CONTEXT_SECTIONS: dict[str, ContextSectionDef] = {
    "standup": ContextSectionDef(
        key="standup",
        label="Standup",
        default_visibility="private",
        questions=[
            "What did you get done?",
            "What's next on your plate?",
            "Anything blocking you?",
            "Any notes to add?",
        ],
        format_template="## {date}\n- Done: {q0}\n- Next: {q1}\n- Blocked: {q2}\n- Note: {q3}\n",
        ai_prompt_file=None,
    ),
    "networking": ContextSectionDef(
        key="networking",
        label="Networking",
        default_visibility="private",
        questions=[
            "Who do you want to talk about?",
            "What's on your mind about them?",
            "Any followup you're planning?",
        ],
        format_template="## {q0} — {date}\n**Notes:** {q1}\n**Followup:** {q2}\n",
        ai_prompt_file=None,
    ),
    "ideas": ContextSectionDef(
        key="ideas",
        label="Ideas",
        default_visibility="private",
        questions=[],               # AI-driven
        format_template=None,       # AI formats the output
        ai_prompt_file="ideas_v1.txt",
        ai_questions_count=6,
    ),
}


# ── Derived section lists (add context types here automatically) ──────────────

_PROFILE_SECTIONS = [
    "identity",
    "role-and-responsibilities",
    "current-projects",
    "team-and-relationships",
    "tools-and-systems",
    "communication-style",
    "goals-and-priorities",
    "preferences-and-constraints",
    "domain-knowledge",
    "decision-log",
]

SECTIONS: list[str] = [*_PROFILE_SECTIONS, *CONTEXT_SECTIONS.keys()]

DEFAULT_VISIBILITY: dict[str, str] = {
    "identity": "public",
    "role-and-responsibilities": "public",
    "current-projects": "public",
    "tools-and-systems": "public",
    "team-and-relationships": "private",
    "communication-style": "private",
    "goals-and-priorities": "private",
    "preferences-and-constraints": "private",
    "domain-knowledge": "private",
    "decision-log": "private",
    **{k: v.default_visibility for k, v in CONTEXT_SECTIONS.items()},
}

InterviewPhase = Literal["interviewing", "reviewing", "complete"]


class WhoIsMeModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class ContactRequest(WhoIsMeModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=5, max_length=200)
    message: str = Field(min_length=1, max_length=2000)


# ── Interview / User models ───────────────────────────────────────────────────

class InterviewSession(WhoIsMeModel):
    session_id: str
    user_id: str | None = None
    history: list[dict] = Field(default_factory=list)   # [{role, content}] Bedrock format
    phase: InterviewPhase = "interviewing"
    questions_asked: int = 0
    questions_total: int = 20
    section_density: dict[str, int] = Field(default_factory=dict)  # section → turn count
    skipped_sections: list[str] = Field(default_factory=list)
    approved_files: dict[str, str] = Field(default_factory=dict)   # section → markdown
    draft_files: dict[str, str] = Field(default_factory=dict)      # section → draft markdown
    created_at: str
    ttl: int | None = None


class User(WhoIsMeModel):
    user_id: str
    email: str
    username: str | None = None
    created_at: str
    token_hash: str | None = None      # SHA-256 of bearer token
    published: bool = False
    visibility: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_VISIBILITY))


# ── Interview API request/response shapes ─────────────────────────────────────

class RespondRequest(WhoIsMeModel):
    text: str = Field(min_length=1, max_length=5000)


class SkipSectionRequest(WhoIsMeModel):
    section: str


class MoreQuestionsRequest(WhoIsMeModel):
    count: int = Field(default=10, ge=1, le=50)


class ReviewApproveRequest(WhoIsMeModel):
    file: str


class ReviewFeedbackRequest(WhoIsMeModel):
    file: str
    text: str = Field(min_length=1, max_length=2000)


class RespondResponse(WhoIsMeModel):
    message: str
    sections_touched: list[str]
    heckle: str | None = None
    questions_remaining: int
    phase: InterviewPhase


# ── User account API shapes ───────────────────────────────────────────────────

class StartAuthRequest(WhoIsMeModel):
    email: str = Field(min_length=5, max_length=200)
    session_id: str | None = None   # link existing interview session on verify


class VerifyAuthRequest(WhoIsMeModel):
    token: str


class UpdateVisibilityRequest(WhoIsMeModel):
    visibility: dict[str, str]


class PublishRequest(WhoIsMeModel):
    username: str = Field(min_length=2, max_length=30, pattern=r"^[a-z0-9_-]+$")


class ContextImportRequest(WhoIsMeModel):
    section: str
    content: str = Field(min_length=1, max_length=500_000)
    merge: Literal["replace", "prepend", "append"] = "prepend"
