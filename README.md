# WhoIsMe

Website and API for [whoisme.io](https://whoisme.io) — AI-conducted interview that builds a personal context portfolio.

## Structure

```
├── ui/       React 19 + Vite 6 + TypeScript + Tailwind CSS 4
├── api/      AWS Lambda + DynamoDB + Bedrock (Claude 3.5 Haiku)
├── assets/   Brand assets (logo, favicon source)
└── scripts/  Smoke tests, session extractor, Cloudflare DNS upsert
```

## Local development

### API

```bash
# Start DynamoDB Local
make local-db-start
make local-db-seed

# Start API (port 3000)
make local-api-start
```

### UI

```bash
cp ui/.env.local.example ui/.env.local
# Fill in VITE_API_URL, VITE_CARTESIA_API_KEY, VITE_INTERVIEWER_VOICE_ID

cd ui && npm install && npm run dev
```

## Deployment

- **UI** → S3 + CloudFront (`deploy-ui.yml`, triggers on push to `main` with changes in `ui/`)
- **API** → AWS Lambda via SAM (`deploy-api.yml`, triggers on push to `main` with changes in `api/`)
- **DNS** → Cloudflare: `api.whoisme.io` CNAME → API Gateway (gray cloud, proxy off)

## Architecture

```
Browser
  └── whoisme.io (CloudFront → S3, React SPA)
        └── api.whoisme.io (API Gateway → Lambda)
              ├── Interview engine      POST /interview, /interview/{id}/*
              └── User accounts         POST /users/start, /users/verify, /users/me/*
```

Profile data is published to **Cloudflare KV** at `whoisme.io/u/{username}` on publish.

Cartesia TTS runs entirely in the browser via WebSocket — no Lambda proxy.

## Interview engine

AI-conducted interview that produces a 10-file personal context portfolio at `whoisme.io/u/{username}`.

**Flow:** `#/interview` → 20 questions → review progress → approve/revise each file → publish

**Ten portfolio files:** identity, role-and-responsibilities, current-projects, team-and-relationships, tools-and-systems, communication-style, goals-and-priorities, preferences-and-constraints, domain-knowledge, decision-log

**Interview API:**

| Endpoint | Purpose |
|----------|---------|
| `POST /interview` | Create session, return first question |
| `POST /interview/{id}/respond` | Submit answer, get next question |
| `POST /interview/{id}/skip-question` | Skip current question |
| `POST /interview/{id}/skip-section` | Skip an entire section |
| `POST /interview/{id}/pause` | End interview early, generate drafts |
| `POST /interview/{id}/more` | Return to interview from review phase |
| `POST /interview/{id}/review/approve` | Approve a draft file |
| `POST /interview/{id}/review/feedback` | Revise a draft with feedback |
| `GET  /interview/{id}` | Get session state |

**User API:**

| Endpoint | Purpose |
|----------|---------|
| `POST /users/start` | Send magic-link email |
| `POST /users/verify` | Verify token, return session token |
| `GET  /users/me` | Get current user profile |
| `PATCH /users/me/visibility` | Set per-section public/private |
| `POST /users/me/publish` | Choose username, write profile to Cloudflare KV |
| `POST /users/me/token` | Generate long-lived bearer token (for MCP access) |
| `DELETE /users/me/token` | Revoke bearer token |

## GitHub secrets required

| Secret | Purpose |
|--------|---------|
| `AWS_ROLE_ARN` | OIDC role for both deploy workflows |
| `S3_BUCKET` | UI bucket name |
| `CLOUDFRONT_DISTRIBUTION_ID` | CloudFront distribution for whoisme.io |
| `VITE_API_URL` | `https://api.whoisme.io` |
| `VITE_CARTESIA_API_KEY` | Cartesia API key (baked into UI build) |
| `VITE_INTERVIEWER_VOICE_ID` | Cartesia voice UUID for interview TTS (optional; random default) |
| `ACM_CERTIFICATE_ARN` | ACM cert for `api.whoisme.io` (us-east-1) |
| `SLACKMAIL_URL` | Slackmail service base URL |
| `SLACKMAIL_API_KEY` | Slackmail API key |
| `CLOUDFLARE_API_TOKEN` | Cloudflare API token for KV writes on publish |
| `CLOUDFLARE_ZONE_ID` | Cloudflare zone ID for whoisme.io |
| `CF_KV_NAMESPACE_ID` | Cloudflare KV namespace for profile storage |
