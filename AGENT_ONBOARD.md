# Sentinel — fresh-agent onboarding / context prompt

Paste this whole file to a fresh coding agent (or read it after SSHing into a new machine). It is
everything needed to run, demo, extend, or debug Sentinel with zero prior context.

---

## What Sentinel is (one paragraph)

Sentinel is an **autonomous, *required* compliance & documentation gate on every pull request**,
powered by **Devin**. When a PR is opened on the target repo, an orchestrator auto-attaches a Devin
session that (in its own container) clones the repo, verifies documentation against the diff and fixes
drift **directly on the feature branch**, runs a **control-mapped static compliance suite** (Trivy,
Semgrep, Bandit, Gitleaks, Hadolint, kube-linter, licenses, + docs-currency), remediates fixable
findings via a **human-approved proxy PR**, posts a **required human-digestible review comment**,
files tickets on a built-in board, and updates the **SSP / POA&M** (each finding mapped to an 800-53
control). A live dashboard shows every instance, PR/CI status, the POA&M burn-down, MTTR, Devin's
plans, and a chat to steer sessions. It is the "human orchestrator + autonomous coder + engineering
notebook + CI-watch + compliance gate" pattern, productized on Devin, for a regulated/federal shop.

## Repos & identities
- **Solution (this repo):** `Soham4001A/CognitionDemo` (product name "Sentinel"). Pushed via a repo
  **deploy key** (`~/.ssh/id_ed25519_cognitiondemo`, alias `github.com-cognitiondemo`).
- **Target (what Sentinel guards):** `Soham4001A/superset-cognition-demo` (fork of apache/superset).
  Pushed via the personal user key (`~/.ssh/id_ed25519_personal`, alias `github.com-personal`,
  identity `Soham4001A <Soham4001A@users.noreply.github.com>`).

## Credentials (in `.env`, gitignored — see `.env.example`)
- `DEVIN_API_KEY` = `apk_user_…` (Devin Settings → API Keys). Base `https://api.devin.ai/v1`, Bearer auth.
- `GH_PERSONAL_TOKEN` = fine-grained PAT on `Soham4001A` (Contents R/W, Issues R/W, Pull requests R/W,
  Commit statuses R/W). Optional for a dry demo (Devin sessions still spawn); **required** for the live
  required-check / PR-comment / proxy-PR actions on the fork.

## Run it (fresh machine)
```bash
./setup.sh            # checks Docker, fills .env, preflights Devin + GitHub, builds
docker compose up     # (or: make up)  → http://localhost:8080
# click "▶ Run Demo"  (or: ./demo.sh [PR_NUMBER]  /  make demo PR=123)
```
`docker compose up` runs ONE container (`sentinel`) that serves both the API and the dashboard on :8080.

## Architecture / file map
- `orchestrator/app/main.py` — FastAPI. Routes: `POST /webhook/github` (pull_request.opened → attach
  Devin), `POST /api/demo/run` (one-click), `POST /api/tickets` (board), `GET /api/state` (dashboard),
  `POST /api/chat` (query state / steer a session). Serves the dashboard at `/`.
- `orchestrator/app/playbook.py` — **the core IP**: the per-PR Devin "job description" (docs-sync,
  scan, proxy-PR, required comment, tickets, POA&M/SSP). The orchestrator does no engineering; this does.
- `orchestrator/app/devin.py` — Devin API client (create/get/list/message + status normalization).
- `orchestrator/app/github_client.py` — set required `devin/compliance` status, PR comment, CI read.
- `orchestrator/app/state.py` — SQLite store + dashboard metrics (MTTR, burn-down).
- `orchestrator/app/poller.py` — background loop: ingest Devin `structured_output`, monitor proxy-PR CI,
  drive the required check.
- `orchestrator/static/index.html` — the SOC-style dashboard (vanilla JS, polls `/api/state`).
- `compliance/` — `SSP.md` + `POAM.md` (control-mapped, Devin-maintained) and `scanners/`
  (`run_scans.sh` = 8 static scanners install-or-skip; `normalize.py` = one control-mapped
  `findings.json` + SBOM; exits 2 on high/critical). `workflows/compliance.yml` is the required Action
  installed on the fork.
- `PLAN.md` — full architecture, the required-gate model, phased build, deliverables, risks, the
  Nexus→Sentinel transposition. `TRACKER.md` — the build notebook (phases → atoms → status).

## The per-PR loop (what Devin does)
1. clone + diff vs base · lightweight bug-hunt
2. docs: build + verify vs diff → fix stale docs, commit to the feature branch (no gate)
3. compliance: `run_scans.sh` → for fixable findings open a **proxy PR** → feature branch (human-approve to merge)
4. required, human-digestible comment on the PR
5. file a ticket per finding (`POST /api/tickets`)
6. append POA&M rows (above `<!-- SENTINEL:POAM-ROWS -->`), update SSP if a control changed

## The "required, not additive" mechanism
- Docs → auto-committed (low-risk). Security → proxy PR (human approval required). Every PR → a
  required `devin/compliance` status + a required review comment. Make `compliance` and `devin/compliance`
  **required checks in branch protection** on the fork to truly gate merges.

## How to extend (next-steps to pitch)
- DAST (ZAP/Nuclei) once a Superset instance is stood up; Schemathesis API fuzz; OpenSCAP/STIG; real
  Nessus. Swap the built-in board for real JIRA/ServiceNow (or an MCP). Multi-repo. Air-gapped/enclave
  deployment (Devin-in-enclave, evidence to the ATO package). Policy-as-code gates.

## Gotchas
- Public webhook delivery needs a tunnel (ngrok/cloudflared) to reach `:8080`. For a laptop demo, the
  **"Run Demo" button / `demo.sh`** posts the PR-opened event to the orchestrator directly — no tunnel.
- A real `POST /api/demo/run` with a live PR spawns a **real Devin session** (costs ACU) and, with the
  PAT, acts on the fork. Use a **pre-staged PR** that deterministically triggers a docs-stale + ≥1
  finding so the demo is reproducible.
- Superset is huge → Devin works diff-scoped; shallow clones.
