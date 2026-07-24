#!/usr/bin/env bash
# Sentinel demo CLI — drive the running orchestrator the same way the dashboard's Demo Control does.
#
#   ./demo.sh reset            clean the fork to a repeatable baseline (closes PRs, deletes sentinel
#                              branches, reopens+unlabels issues, wipes the board)
#   ./demo.sh seed             ensure the 5 control-mapped issues exist (open + unlabeled)
#   ./demo.sh issue <N>        Devin remediates issue #N → opens a PR that `Closes #N`
#   ./demo.sh pr <N>           Devin reviews/gates PR #N (compliance gate)
#   ./demo.sh gate-pr          open a fresh deliberately-flawed PR that triggers the gate
#   ./demo.sh                  synthetic PR-review demo (no args)
set -uo pipefail
URL="${SENTINEL_URL:-http://localhost:8080}"
J(){ command -v jq >/dev/null && jq . || cat; }
post(){ curl -sS -m 40 -X POST "$URL$1" -H 'content-type: application/json' ${2:+-d "$2"} | J; }

case "${1:-}" in
  reset)    post /api/demo/reset ;;
  seed)     post /api/demo/seed ;;
  gate-pr)  post /api/demo/seed_pr ;;
  issue)    [ -n "${2:-}" ] || { echo "usage: ./demo.sh issue <N>"; exit 1; }; post /api/demo/remediate "{\"issue\":$2}" ;;
  pr)       [ -n "${2:-}" ] || { echo "usage: ./demo.sh pr <N>"; exit 1; };    post /api/demo/run "{\"pr\":$2}" ;;
  "")       post /api/demo/run '{}' ;;
  *)        echo "unknown command: $1"; sed -n '3,12p' "$0"; exit 1 ;;
esac
echo "→ watch it play out at $URL"
