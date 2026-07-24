# Sentinel — Build Tracker

The engineering-notebook for this build (the Nexus discipline Sentinel productizes). Phases → atoms → status.

## Status board

| Phase | Atom | Status |
|---|---|---|
| 0 Setup | fork, keys, deploy key, Devin verified, repo live | ✅ done |
| 1 Compliance baseline | `SSP.md` + `POAM.md` seeds (fork + solution) | ✅ done |
| 1 | scanner suite `run_scans.sh` + `normalize.py` (8 static, control-mapped) | ✅ done (unit-tested) |
| 1 | `compliance.yml` required-check Action on fork | ✅ done (installed) |
| 2 Orchestrator | `devin.py` (create/get/list/message) | ✅ done |
| 2 | `github_client.py` (required check, comment, CI read) | ✅ done |
| 2 | `state.py` (SQLite) + `poller.py` (session + CI poll loop) | ✅ done |
| 2 | `main.py` webhook → playbook → session → required-check | ✅ done (smoke-tested) |
| 3 Playbook | `playbook.py` (docs + scan + proxy-PR + comment + ticket + POA&M) | ✅ done |
| 5 Board | built-in ticket board API (`POST /api/tickets`) | ✅ done (Kanban UI = Phase 4) |
| 4 Dashboard | tiles · instances/PR/CI table · burn-down · Kanban · timeline | ✅ done |
| 4 | chat → orchestrator (state + steer session via `@id`) | ✅ done |
| 6 Docker | `docker compose up --build` clean (one container, dashboard+API) | ✅ done (verified in-container) |
| 8 Packaging | `setup.sh` + preflight · "Run Demo" button + `demo.sh` + `Makefile` · `AGENT_ONBOARD.md` | ✅ done |
| 6 Deliver | README · `LOOM.md` (5-min script) | ✅ done |
| Demo prep | deterministic demo PR staged on fork (`demo/sentinel-showcase`) | ✅ done |
| — E2E | fire ONE real Devin session on the demo PR (needs `GH_PERSONAL_TOKEN` + ACU) | ⬜ **gated on operator** |
| — Branch protection | make `compliance` + `devin/compliance` required checks on fork | ⬜ needs PAT/admin |

## Decisions log
- **Ticket board:** built-in (dashboard-hosted), not external JIRA (no license). API for Devin to file into.
- **Scanners:** Trivy, Trivy-SBOM, Semgrep, Bandit, Gitleaks, Hadolint, kube-linter, license — all static. DAST (ZAP) → next-steps.
- **Required model:** docs auto-commit to feature branch (no gate); security → proxy PR (human-approval required); Devin's info comment required on every PR.
- **Webhook for demo:** the "Run Demo" button POSTs the PR-opened event to the orchestrator directly (no public tunnel needed on a laptop). Real GitHub webhook delivery documented via a tunnel for production.
- **Repos:** solution = `Soham4001A/CognitionDemo` (product "Sentinel"); target = `Soham4001A/superset-cognition-demo` (fork).

## Notes / gotchas
- Phase 2 functional test needs `GH_PERSONAL_TOKEN` in `.env` (fork comments/checks/PRs).
- Superset is huge → Devin works diff-scoped; shallow clones.
