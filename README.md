# t12n.ai

Website and API for [t12n.ai](https://t12n.ai) — AI Transformation Consulting.

## Structure

```
├── ui/       React 19 + Vite 6 + TypeScript + Tailwind CSS 4
├── api/      AWS Lambda + DynamoDB + Bedrock (Claude 3.5 Haiku)
├── assets/   Brand assets (logo, rabbit, favicon source)
└── scripts/  Smoke tests, session extractor
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
- **DNS** → Cloudflare: `api.t12n.ai` CNAME → API Gateway (gray cloud, proxy off)

## Architecture

```
Browser
  └── t12n.ai (CloudFront → S3, React SPA)
        └── api.t12n.ai (API Gateway → Lambda)
              ├── GET  /conversations/icebreakers     → random icebreaker from DynamoDB
              └── POST /conversations/{id}/turns      → save turn, call Bedrock for consultant replies
```

Cartesia TTS runs entirely in the browser via WebSocket — no Lambda proxy.

## Conversation engine

The site runs a three-speaker conversation between the visitor and two AI consultants:

- **Visitor** — types or speaks their message; played back via Cartesia TTS before submission
- **Alex** (`consultant1`) — warm transformation expert; reflects, asks sharp questions
- **Jamie** (`consultant2`) — wildly funny devil's advocate; absurd analogies, dinner-party wit

Each visitor turn is saved to DynamoDB, then the full conversation history is sent to **Claude 3.5 Haiku** (via Bedrock cross-region inference) with a system prompt enforcing 15–25 word replies per consultant. Both replies are returned to the UI, displayed as chat bubbles, and spoken sequentially via Cartesia TTS.

### Speakers & voices

| Speaker | Persona | Cartesia voice |
|---------|---------|----------------|
| Visitor | Site visitor | Configured via `VITE_CARTESIA_VOICE_ID` |
| Alex (`consultant1`) | Warm transformation expert | Tessa — Kind Companion |
| Jamie (`consultant2`) | Whimsical devil's advocate | Clint — Rugged Actor |

## GitHub secrets required

| Secret | Purpose |
|--------|---------|
| `AWS_ROLE_ARN` | OIDC role for both deploy workflows |
| `S3_BUCKET` | UI bucket name |
| `CLOUDFRONT_DISTRIBUTION_ID` | CloudFront distribution for t12n.ai |
| `VITE_API_URL` | `https://api.t12n.ai` |
| `VITE_CARTESIA_API_KEY` | Cartesia API key (baked into UI build) |
| `VITE_CARTESIA_VOICE_ID` | Cartesia voice UUID |
| `ACM_CERTIFICATE_ARN` | ACM cert for api.t12n.ai (us-east-1) |
