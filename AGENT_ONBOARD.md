# Sentinel — fresh-agent onboarding / context prompt

Paste this whole file to a fresh coding agent (or read it after SSHing into a new machine). It is
everything needed to run, demo, extend, or debug Sentinel with zero prior context.

---

## What Sentinel is (one paragraph)

Sentinel wires **Devin** into a GitHub repo's events as an autonomous teammate, via two loops. **(1)
Issue remediation:** a filed issue labeled `sentinel:remediate` triggers a Devin session that fixes it
in its own container and opens a PR that `Closes #N`. **(2) PR compliance gate:** when any PR opens,
Devin auto-attaches as a *required reviewer* — verifies docs against the diff (fixing drift on the
branch), runs a control-mapped static scan suite, remediates fixable security findings via a
human-approved **proxy PR**, posts one unified verdict comment, files tickets, and updates the
**SSP/POA&M** (each finding mapped to an 800-53 control) — and **blocks merge** via a required
`devin/compliance` check until it's satisfied. The orchestrator does **zero engineering**; it routes
events, dispatches/observes Devin, and drives GitHub's merge gate. A live dashboard shows both loops
as concrete cards, a findings-by-control burn-down, MTTR, an audit trail, and a **Demo Control** panel.

## Repos & identities
- **Solution (this repo):** `Soham4001A/CognitionDemo` (product "Sentinel"). Pushed via a repo
  **deploy key** (`~/.ssh/id_ed25519_cognitiondemo`, SSH alias `github.com-cognitiondemo`).
- **Target (what Sentinel guards):** `Soham4001A/superset-cognition-demo` (fork of apache/superset).
  Has the compliance kit, the required `devin/compliance` branch-protection check, and 5 seeded
  control-mapped issues.

## Credentials (in `.env`, gitignored — see `.env.example`)
- `DEVIN_API_KEY` = `apk_user_…` (Devin → Settings → API Keys). Base `https://api.devin.ai/v1`, Bearer.
- `GH_PERSONAL_TOKEN` = fine-grained PAT on the fork (Contents / Issues / Pull requests / Commit
  statuses / **Administration** R/W). Optional for a dry run; **required** for live checks/PRs/issues.
- `PUBLIC_URL` = public base for webhook delivery (a `cloudflared` tunnel to `:8080`). The Demo Control
  buttons hit localhost directly, so the core demo works without it.

## Run it (fresh machine)
```bash
./setup.sh            # checks Docker, fills .env, preflights Devin + GitHub, builds
docker compose up     # (or: make up)  → http://localhost:8080   (walkthrough at /how-it-works.html)
```
ONE container (`sentinel`) serves both the API and the dashboard on :8080. State is SQLite in `./data`.

## Drive the demo (dashboard "Demo Control", or `./demo.sh <cmd>`)
- `reset` — close all open PRs, delete sentinel/* branches, reopen + unlabel issues, wipe the board (teardown only; never starts Devin)
- `seed` — ensure the 5 control-mapped issues exist
- `issue <N>` — Devin remediates issue #N → PR that `Closes #N`   ← the hook
- `gate-pr` — open a fresh deliberately-flawed PR → Devin's compliance gate
- `pr <N>` — Devin reviews an existing PR

## Architecture / file map
- `orchestrator/app/main.py` — FastAPI. Webhooks: `issues` (labeled → remediate), `pull_request`
  (opened → gate), `issue_comment` (@sentinel/@devin → gate). Demo-control API (`/api/demo/{reset,
  seed,seed_pr,remediate,run}`), `/api/tickets`, `/api/state`, `/api/chat`. Serves the dashboard at `/`.
- `orchestrator/app/playbook.py` — **the core IP**: `build_playbook` (PR review) + `build_remediation_playbook`
  (issue fix). The orchestrator does no engineering; these prompts are the product.
- `orchestrator/app/poller.py` — one async loop tracking every session; drives `devin/compliance` to
  resolution. Re-pins the check to the PR's live head, idempotent writes, resolves on merge; tracks
  issue-remediation tasks (issue → PR → closed) and derives each card's summary from the PR body.
- `orchestrator/app/github_client.py` — commit statuses, PRs, issues, branches, demo-reset ops.
- `orchestrator/app/devin.py` — Devin API client (create/get/list/message + status normalization).
- `orchestrator/app/state.py` — SQLite (reviews · tasks · findings · tickets · events) + metrics; `reset()`.
- `orchestrator/static/index.html` — the dashboard (vanilla JS, polls `/api/state`, Demo Control).
- `orchestrator/static/how-it-works.html` — visual walkthrough incl. the "Under the hood" tech breakdown.
- `compliance/` — `SSP.md` + `POAM.md` (control-mapped, Devin-maintained) · `scanners/` (`run_scans.sh`
  = 8 static scanners install-or-skip; `normalize.py` = one control-mapped `findings.json` + SBOM,
  exits 2 on high/critical) · `workflows/compliance.yml` (the Action installed on the fork).
- `README.md` · `PLAN.md` · `TRACKER.md` — overview · architecture/plan · build notebook.

## The two loops (what Devin does)
**Issue:** clone → locate + fix the issue (scanner evidence before/after) → PR `Closes #N` → comment on
the issue → ticket + POA&M. Human merges → issue auto-closes → task resolved.
**PR:** set `devin/compliance` pending → docs fixed+committed to branch (no gate) → scan suite →
proxy PR for security (human-approve) → ONE unified comment (subsumes Devin's native review) → tickets +
POA&M. Gate resolves when the proxy PR merges.

## The "required, not additive" mechanism
Docs auto-commit (low-risk); security → human-approved proxy PR; every PR → a required `devin/compliance`
status. `devin/compliance` is the single required check in the fork's branch protection, so a PR
genuinely cannot merge until Sentinel is green.

## How to extend (next-steps to pitch)
DAST (ZAP/Nuclei) once a Superset instance is up; Schemathesis API fuzz; OpenSCAP/STIG; real Nessus.
Swap the built-in board for JIRA/ServiceNow (or an MCP). Multi-repo. Air-gapped/enclave deployment
(Devin-in-enclave, evidence to the ATO package). Policy-as-code gates.

## Gotchas
- Public webhook delivery needs a tunnel (`cloudflared tunnel --url http://localhost:8080`) → put the
  https URL in `PUBLIC_URL` and point a repo webhook at `<PUBLIC_URL>/webhook/github`. Demo Control
  buttons don't need it.
- Live demo actions spawn **real Devin sessions** (cost ACU). Self-recursion is guarded: `sentinel/*`
  branches and Devin-authored PRs never re-trigger a review.
- Once a remediation PR **merges to master**, that issue's fix is on master — re-remediating the *same*
  issue is a no-op. Use a different open issue, or don't merge during a take. `reset` does not un-merge.
- Superset is huge → Devin works diff-scoped / shallow clones.
