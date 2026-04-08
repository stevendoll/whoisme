#!/usr/bin/env bash
# Upsert a Cloudflare DNS record (create if absent, update if present).
# Usage: CF_ZONE_ID=... CF_API_TOKEN=... ./scripts/cf-dns-upsert.sh <name> <content> [type] [proxied]
set -euo pipefail

NAME="${1:?record name required}"
CONTENT="${2:?record content required}"
TYPE="${3:-CNAME}"
PROXIED="${4:-false}"

BASE="https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID:?CF_ZONE_ID required}/dns_records"
AUTH=(-H "Authorization: Bearer ${CF_API_TOKEN:?CF_API_TOKEN required}")

RECORD_ID=$(curl -sf "$BASE?name=$NAME&type=$TYPE" "${AUTH[@]}" | \
  python3 -c "import sys,json; r=json.load(sys.stdin)['result']; print(r[0]['id'] if r else '')")

PAYLOAD=$(jq -n \
  --arg type "$TYPE" --arg name "$NAME" --arg content "$CONTENT" --argjson proxied "$PROXIED" \
  '{type: $type, name: $name, content: $content, ttl: 1, proxied: $proxied}')

if [ -n "$RECORD_ID" ]; then
  RESULT=$(curl -sf -X PUT "$BASE/$RECORD_ID" "${AUTH[@]}" -H "Content-Type: application/json" -d "$PAYLOAD")
  ACTION="Updated"
else
  RESULT=$(curl -sf -X POST "$BASE" "${AUTH[@]}" -H "Content-Type: application/json" -d "$PAYLOAD")
  ACTION="Created"
fi

echo "$RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin); print('$ACTION $NAME' if r['success'] else f'Error: {r[\"errors\"]}')"
