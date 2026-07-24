#!/usr/bin/env bash
# Sentinel one-shot bootstrap — idempotent. Run on a fresh machine:
#   ./setup.sh   (then: docker compose up  → open http://localhost:8080 → click "Run Demo")
set -uo pipefail
cd "$(dirname "$0")"
ok(){ printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn(){ printf '  \033[33m!\033[0m %s\n' "$*"; }
die(){ printf '  \033[31m✗ %s\033[0m\n' "$*"; exit 1; }

echo "── Sentinel setup ─────────────────────────────────────────────"

# 1. prerequisites
command -v docker >/dev/null || die "Docker not found — install Docker Desktop / engine first."
docker compose version >/dev/null 2>&1 || die "docker compose plugin not found."
command -v curl >/dev/null || die "curl not found."
ok "docker + compose + curl present"

# 2. .env
if [ ! -f .env ]; then
  cp .env.example .env
  warn "created .env from template — fill in your keys:"
  if [ -t 0 ]; then
    read -r -p "    DEVIN_API_KEY (apk_user_…): " k;  [ -n "$k" ] && sed -i.bak "s|^DEVIN_API_KEY=.*|DEVIN_API_KEY=$k|" .env
    read -r -p "    GH_PERSONAL_TOKEN (optional, Enter to skip): " g; [ -n "$g" ] && sed -i.bak "s|^GH_PERSONAL_TOKEN=.*|GH_PERSONAL_TOKEN=$g|" .env
    rm -f .env.bak
  else
    warn "non-interactive shell — edit .env by hand, then re-run."; exit 1
  fi
fi
set -a; . ./.env; set +a
[ -n "${DEVIN_API_KEY:-}" ] || die "DEVIN_API_KEY empty in .env"
ok ".env loaded"

# 3. preflight — Devin reachable + key valid
code=$(curl -sS -m 15 -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $DEVIN_API_KEY" \
  https://api.devin.ai/v1/sessions?limit=1 || echo 000)
[ "$code" = "200" ] && ok "Devin API: authenticated (HTTP 200)" || die "Devin API preflight failed (HTTP $code) — check DEVIN_API_KEY"

# 4. preflight — GitHub token (optional but needed for live PR actions)
if [ -n "${GH_PERSONAL_TOKEN:-}" ]; then
  gcode=$(curl -sS -m 15 -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $GH_PERSONAL_TOKEN" https://api.github.com/user || echo 000)
  [ "$gcode" = "200" ] && ok "GitHub token: valid" || warn "GitHub token invalid (HTTP $gcode) — live PR actions will be off"
else
  warn "no GH_PERSONAL_TOKEN — the demo still spawns real Devin sessions; live required-check/PR comments are off"
fi

# 5. build
mkdir -p data
echo "  building image…"
docker compose build >/dev/null 2>&1 && ok "image built" || die "docker compose build failed — run 'docker compose build' to see why"

echo "───────────────────────────────────────────────────────────────"
ok "Setup complete."
echo "    Run:   docker compose up        →  http://localhost:8080   (walkthrough: /how-it-works.html)"
echo ""
echo "    Then drive it from the dashboard's Demo Control, or the CLI:"
echo "      ./demo.sh reset               clean the fork to a repeatable baseline"
echo "      ./demo.sh issue 5             Devin remediates issue #5 → PR that Closes #5"
echo "      ./demo.sh gate-pr             open a flawed PR → Devin's compliance gate"
echo "    (make up / make down / make logs also available.)"
