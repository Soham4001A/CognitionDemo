# Sentinel — Build Tracker

The engineering-notebook for this build (the Nexus discipline Sentinel productizes). Phases → atoms → status.

## Status board

| Phase | Atom | Status |
|---|---|---|
| 0 Setup | fork, keys, deploy key, Devin verified, repo live | ✅ done |
| 1 Compliance baseline | `compliance/SSP.md` + `POAM.md` seeds (on fork) | ⏳ in progress |
| 1 | scanner suite `compliance/scanners/` + `run_scans.sh` (8 static scanners) | ⏳ |
| 1 | `.github/workflows/compliance.yml` on fork (required-check surface) | ⏳ |
| 2 Orchestrator | `devin.py` (create/get/list/message) | ⬜ |
| 2 | `github_client.py` (checks, comments, CI read, proxy PR) | ⬜ |
| 2 | `state.py` (SQLite) + `poller.py` (session + CI poll loop) | ⬜ |
| 2 | `main.py` webhook → playbook → session → required-check | ⬜ |
| 3 Playbook | finalize `playbook.py` (docs + scan + proxy-PR + comment + ticket + POA&M) | ⬜ |
| 4 Dashboard | instances · PRs+CI · findings/POA&M burn-down · plans | ⬜ |
| 4 | chat → orchestrator (state + steer session) | ⬜ |
| 5 Board | built-in ticket board (API + Kanban) | ⬜ |
| 6 Docker | `docker compose up` clean | ⬜ |
| 8 Packaging | `setup.sh` · "Run Demo" button + `demo.sh` · `AGENT_ONBOARD.md` | ⬜ |
| 6 Deliver | README · Loom script | ⬜ |

## Decisions log
- **Ticket board:** built-in (dashboard-hosted), not external JIRA (no license). API for Devin to file into.
- **Scanners:** Trivy, Trivy-SBOM, Semgrep, Bandit, Gitleaks, Hadolint, kube-linter, license — all static. DAST (ZAP) → next-steps.
- **Required model:** docs auto-commit to feature branch (no gate); security → proxy PR (human-approval required); Devin's info comment required on every PR.
- **Webhook for demo:** the "Run Demo" button POSTs the PR-opened event to the orchestrator directly (no public tunnel needed on a laptop). Real GitHub webhook delivery documented via a tunnel for production.
- **Repos:** solution = `Soham4001A/CognitionDemo` (product "Sentinel"); target = `Soham4001A/superset-cognition-demo` (fork).

## Notes / gotchas
- Phase 2 functional test needs `GH_PERSONAL_TOKEN` in `.env` (fork comments/checks/PRs).
- Superset is huge → Devin works diff-scoped; shallow clones.
