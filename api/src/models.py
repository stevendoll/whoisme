from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from typing import Literal


class WhoIsMeModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class Icebreaker(WhoIsMeModel):
    icebreaker_id: str
    text: str
    is_active: str = "true"
    created_at: str


class IcebreakerResponse(WhoIsMeModel):
    id: str
    text: str


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
