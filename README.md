# Sentinel — autonomous, required compliance & docs gate on every PR (powered by Devin)

Sentinel auto-attaches Devin to every freshly-opened PR as a **required reviewer**: it verifies
docs against the diff, runs a compliance scan suite, fixes what it can, opens a reviewable proxy
PR for security changes, files a ticket + updates the SSP/POA&M, and blocks merge until satisfied.

See `../PLAN.md` for the full architecture and the Nexus→Sentinel transposition.

## Run
```bash
cp ../.env .env            # DEVIN_API_KEY + GH_PERSONAL_TOKEN
docker compose up --build  # orchestrator :8080, dashboard :8081
```

## Layout
- `orchestrator/` — FastAPI brain: GH webhook → Devin session → poll → required-check → state → dashboard API + chat
- `dashboard/`    — web UI: instances · PRs+CI · findings/POA&M burn-down · plans · chat
- `compliance/`   — seed SSP.md + POA&M.md (Devin-maintained) + scanner configs
