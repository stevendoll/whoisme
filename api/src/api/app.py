"""
WhoIsMe API — Lambda handler.

Routes:
  POST /contacts                            — contact form submission
  POST /errors                              — client error reporting
  POST /interview                           — start interview session
  POST /interview/{id}/respond              — submit answer, get next question
  POST /interview/{id}/skip                 — skip current section
  POST /interview/{id}/pause                — enter review phase
  POST /interview/{id}/review/approve       — approve a draft file
  POST /users/start                         — send magic link
  POST /users/verify                        — verify magic link token
  GET  /users/me                            — get user profile
  POST /users/me/publish                    — publish profile
"""

from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, CORSConfig
from aws_lambda_powertools.utilities.typing import LambdaContext

import db  # noqa: F401
from api.routers import contacts, errors, auth, interview, users

logger  = Logger(service="whoisme-api")
metrics = Metrics(namespace="WhoIsMeApi")

api = APIGatewayHttpResolver(cors=CORSConfig(allow_origin="*"))

api.include_router(contacts.router)  # POST /contacts
api.include_router(errors.router)    # POST /errors
api.include_router(auth.router)      # POST /admin/login, POST /admin/verify
api.include_router(interview.router) # POST /interview, /interview/{id}/*
api.include_router(users.router)     # POST /users/start, /users/verify, /users/me/*


@logger.inject_lambda_context(log_event=False)
def handler(event: dict, context: LambdaContext) -> dict:
    if event.get("source") == "warmup":
        logger.info("Warmup ping — skipping resolver")
        return {"statusCode": 200}
    return api.resolve(event, context)
