#!/usr/bin/env bash
# Trigger the Sentinel demo via the running orchestrator (equivalent to the dashboard "Run Demo" button).
#   ./demo.sh [PR_NUMBER]   (no arg = synthetic demo PR; a number = review that real PR on the fork)
set -uo pipefail
URL="${SENTINEL_URL:-http://localhost:8080}"
PR="${1:-}"
curl -sS -m 20 -X POST "$URL/api/demo/run" -H 'content-type: application/json' \
  -d "$([ -n "$PR" ] && echo "{\"pr\":$PR}" || echo '{}')" | (command -v jq >/dev/null && jq . || cat)
echo
echo "→ watch it play out at $URL"
