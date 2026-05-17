# WhoIsMe

Website and API for [whoisme.io](https://whoisme.io) — AI-conducted interview that builds a personal context portfolio.

Inspired by the concept of a [personal context portfolio](https://play.aidailybrief.ai/episodes/personal-context-portfolio/) from AI Daily Brief.

## Structure

```
├── ui/       React 19 + Vite 6 + TypeScript + Tailwind CSS 4
├── api/      AWS Lambda + DynamoDB + Bedrock (Claude 3.5 Haiku)
├── assets/   Brand assets (logo, favicon source)
├── docs/     Internal notes and standup history
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
# Fill in VITE_API_URL, VITE_CARTESIA_API_KEY, VITE_CARTESIA_VOICE_ID

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
              ├── Documents             GET|POST /documents, /documents/{id}/*
              └── User accounts         POST /users/start, /users/verify, /users/me/*
```

Profile data is published to **Cloudflare KV** at `whoisme.io/u/{username}` on publish.

Cartesia TTS runs entirely in the browser via WebSocket — no Lambda proxy.

**DynamoDB tables:** `whoisme-contacts`, `whoisme-admin-tokens`, `whoisme-users`, `whoisme-user-tokens`, `whoisme-interview-sessions`, `whoisme-documents`, `whoisme-document-versions`

## Interview engine

AI-conducted interview that produces a 10-section personal context portfolio, accessible at `whoisme.io/u/{username}` and manageable at `#/docs`.

**Flow:** `#/interview` → 20 questions → review drafts → approve/revise each section → publish

Approving a section during review immediately creates a versioned document in the documents table. The `#/docs` page provides a slide-out editor with version history and draft/publish workflow.

**Ten portfolio sections:** identity, role-and-responsibilities, current-projects, team-and-relationships, tools-and-systems, communication-style, goals-and-priorities, preferences-and-constraints, domain-knowledge, decision-log

**Quick context sessions** support structured short-form entries (standup, networking) via `POST /interview?context_type=<type>`.

**Interview API:**

| Endpoint | Purpose |
|----------|---------|
| `POST /interview` | Create session, return first question |
| `POST /interview/{id}/respond` | Submit answer, get next question |
| `POST /interview/{id}/skip-question` | Skip current question |
| `POST /interview/{id}/skip-section` | Skip an entire section |
| `POST /interview/{id}/reactivate-section` | Re-enable a skipped section |
| `POST /interview/{id}/pause` | End interview early, generate drafts |
| `POST /interview/{id}/more` | Return to interview from review phase |
| `POST /interview/{id}/review/approve` | Approve a draft section |
| `POST /interview/{id}/review/feedback` | Revise a draft with feedback |
| `POST /interview/{id}/context-end` | End a quick context session |
| `GET  /interview/{id}` | Get session state |

**Documents API:**

| Endpoint | Purpose |
|----------|---------|
| `GET  /documents` | List all documents for current user |
| `POST /documents` | Create a new document |
| `POST /documents/{id}/versions` | Save a new draft version |
| `GET  /documents/{id}/versions` | List version history |
| `POST /documents/{id}/versions/{vid}/publish` | Publish a version |

**User API:**

| Endpoint | Purpose |
|----------|---------|
| `POST /users/start` | Send magic-link email |
| `POST /users/verify` | Verify token, return session token |
| `GET  /users/me` | Get current user profile |
| `GET  /users/me/files` | Get merged approved files |
| `PATCH /users/me/visibility` | Set per-section public/private |
| `POST /users/me/publish` | Choose username, write profile to Cloudflare KV |
| `POST /users/me/unpublish` | Remove profile from Cloudflare KV |
| `POST /users/me/import` | Link an interview session to account |
| `POST /users/me/context-publish` | Publish a quick context session result |
| `POST /users/me/context-import` | Import external content into a context section |
| `GET  /sections/context` | List available quick context section types |
| `POST /users/me/token` | Generate long-lived bearer token (for MCP access) |
| `DELETE /users/me/token` | Revoke bearer token |
| `DELETE /users/me` | Delete account |

## GitHub secrets required

| Secret | Purpose |
|--------|---------|
| `AWS_ROLE_ARN` | OIDC role for both deploy workflows |
| `S3_BUCKET` | UI bucket name |
| `CLOUDFRONT_DISTRIBUTION_ID` | CloudFront distribution for whoisme.io |
| `VITE_API_URL` | `https://api.whoisme.io` |
| `VITE_CARTESIA_API_KEY` | Cartesia API key (baked into UI build) |
| `VITE_CARTESIA_VOICE_ID` | Cartesia voice UUID for interview TTS |
| `VITE_CARTESIA_VOICES` | JSON map of named voices |
| `ACM_CERTIFICATE_ARN` | ACM cert for `api.whoisme.io` (us-east-1) |
| `CF_ACCOUNT_ID` | Cloudflare account ID |
| `CLOUDFLARE_API_TOKEN` | Cloudflare API token for KV writes on publish |
| `CLOUDFLARE_ZONE_ID` | Cloudflare zone ID for whoisme.io |
| `CF_KV_NAMESPACE_ID` | Cloudflare KV namespace for profile storage |
| `SLACKMAIL_URL` | Slackmail service base URL |
| `SLACKMAIL_API_KEY` | Slackmail API key |
| `SMOKE_TEST_USERNAME` | Published username used in post-deploy smoke test |
