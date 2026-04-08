"""
WhoIsMe API — Lambda handler.

Routes:
  GET  /conversations/icebreakers           — random active icebreaker
  GET  /conversations                       — list conversations (history)
  GET  /conversations/{id}/turns            — all turns for a conversation
  POST /conversations/{id}/turns            — save turn; visitor turns trigger Bedrock replies
  POST /contacts                            — save contact form submission
  GET  /admin/icebreakers                   — list all icebreakers
  POST /admin/icebreakers                   — create icebreaker
  PATCH /admin/icebreakers/{id}             — update icebreaker
  DELETE /admin/icebreakers/{id}            — delete icebreaker
  GET  /admin/ideas                         — list all conversation ideas
  POST /admin/ideas                         — create idea
  PATCH /admin/ideas/{id}                   — update idea (toggle is_active, etc.)
  POST /errors                              — client error reporting (TTS failures → Slack + SNS)

Environment variables:
  ICEBREAKERS_TABLE   — DynamoDB table name
  TURNS_TABLE         — DynamoDB table name
  CONVERSATIONS_TABLE — DynamoDB table name
  CONTACTS_TABLE      — DynamoDB table name
  IDEAS_TABLE         — DynamoDB table name
"""

from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, CORSConfig
from aws_lambda_powertools.utilities.typing import LambdaContext

import db  # noqa: F401
from api.routers import icebreakers, turns, admin, contacts, conversations, ideas_admin, errors, auth, interview, users

logger  = Logger(service="whoisme-api")
metrics = Metrics(namespace="WhoIsMeApi")

api = APIGatewayHttpResolver(cors=CORSConfig(allow_origin="*"))

# Order matters: more-specific paths first
api.include_router(icebreakers.router)   # GET /conversations/icebreakers
api.include_router(conversations.router) # GET /conversations, GET /conversations/{id}/turns
api.include_router(turns.router)         # POST /conversations/{id}/turns
api.include_router(contacts.router)      # POST /contacts
api.include_router(admin.router)         # /admin/icebreakers
api.include_router(ideas_admin.router)   # /admin/ideas
api.include_router(errors.router)        # POST /errors
api.include_router(auth.router)          # POST /admin/login, POST /admin/verify
api.include_router(interview.router)     # POST /interview, /interview/{id}/*
api.include_router(users.router)         # POST /users/start, /users/verify, /users/me/*


@logger.inject_lambda_context(log_event=False)
def handler(event: dict, context: LambdaContext) -> dict:
    if event.get("source") == "warmup":
        logger.info("Warmup ping — skipping resolver")
        return {"statusCode": 200}
    return api.resolve(event, context)
