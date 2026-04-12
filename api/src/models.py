from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from typing import Literal

SECTIONS = [
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
}

InterviewPhase = Literal["interviewing", "reviewing", "complete"]


class WhoIsMeModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


Speaker = Literal["visitor", "consultant1", "consultant2"]


class TurnRequest(WhoIsMeModel):
    order: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=2000)
    speaker: Speaker
    voices: dict[str, str] | None = None  # {speaker: cartesia_voice_id}


class Turn(WhoIsMeModel):
    conversation_id: str
    order: int
    text: str
    speaker: Speaker
    voice_id: str | None = None
    idea_id: str | None = None
    created_at: str


class ConsultantReply(WhoIsMeModel):
    order: int
    text: str
    speaker: Literal["consultant1", "consultant2"]
    voice_id: str | None = None
    emotion: str | None = None


class TurnResponse(WhoIsMeModel):
    turn: Turn
    consultant_replies: list[ConsultantReply] | None = None


class Conversation(WhoIsMeModel):
    conversation_id: str
    created_at: str
    preview: str
    voices: dict[str, str] | None = None
    used_ideas: list[str] = Field(default_factory=list)


class ContactRequest(WhoIsMeModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=5, max_length=200)
    message: str = Field(min_length=1, max_length=2000)


class Idea(WhoIsMeModel):
    idea_id: str
    text: str
    description: str
    is_active: bool = True
    insertion_type: str                  # "fixed" | "random"
    fixed_turn: int | None = None        # visitor turn number that triggers it (fixed only)
    is_once_only: bool = False           # if True, fires at most once per conversation


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
