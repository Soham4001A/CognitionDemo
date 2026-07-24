# Sentinel

**An autonomous, _required_ compliance & documentation gate on every pull request — powered by [Devin](https://devin.ai).**

Everyone builds *"Devin, go build ticket X → PR."* Sentinel inverts it: Devin **auto-attaches to every
freshly-opened PR** as a **required reviewer**. It clones the repo in its own container, verifies docs
against the diff, runs a control-mapped compliance scan suite, fixes what it can, opens a reviewable
**proxy PR** for the risky changes, files tickets, updates the **SSP/POA&M**, and **blocks merge** until
it's satisfied and a human has approved the security changes. It's the orchestration pattern a regulated
(federal/ATO) shop already runs by hand — productized on Devin.

## Quickstart

```bash
./setup.sh          # checks Docker, fills .env (DEVIN_API_KEY, GH_PERSONAL_TOKEN), preflights, builds
docker compose up   # (or: make up)  → http://localhost:8080
# in the dashboard: click "▶ Run Demo"   (headless: ./demo.sh [PR_NUMBER]  /  make demo PR=123)
```

One container (`sentinel`) serves the API **and** the dashboard on `:8080`.

## The loop (per PR)

```
PR opened → orchestrator sets required check "devin/compliance = pending" → dispatches Devin
Devin (own container): clone+diff → verify docs (fix → commit to feature branch, no gate)
   → run scan suite → open PROXY PR (human-approve to merge) → required review comment
   → file tickets → update SSP/POA&M (finding → 800-53 control)
Dashboard: instances · PR/CI status · POA&M burn-down · MTTR · plans · chat (steer sessions)
```

**Required, not additive:** docs auto-commit (low-risk); security → proxy PR (human approval required);
every PR gets a required `devin/compliance` status + a required review comment. Make those required
checks in branch protection to truly gate merges.

## Compliance suite (control-mapped, static)

Trivy (RA-5/SI-2) · Trivy-SBOM (SR-3/4) · Semgrep + Bandit (SA-11) · Gitleaks (IA-5/SC-28) ·
Hadolint + kube-linter (CM-6/7) · license check (SR-3) · docs-currency (CM-2/3, SA-5).
Each finding becomes a POA&M item tied to its control. (DAST/OpenSCAP/Nessus → next-steps.)

## Layout

| Path | What |
|---|---|
| `orchestrator/app/playbook.py` | **core IP** — the per-PR Devin job description |
| `orchestrator/app/main.py` | FastAPI: webhook · demo · tickets · state · chat · serves the dashboard |
| `orchestrator/app/{devin,github_client,state,poller}.py` | Devin client · GitHub client · SQLite state · poll loop |
| `orchestrator/static/index.html` | SOC-style dashboard |
| `compliance/` | SSP + POA&M (Devin-maintained) · `scanners/` · required `compliance.yml` Action |
| `PLAN.md` · `TRACKER.md` · `AGENT_ONBOARD.md` | architecture · build notebook · fresh-agent context |

## Config (`.env`, gitignored — see `.env.example`)
- `DEVIN_API_KEY` — `apk_user_…` (Devin → Settings → API Keys).
- `GH_PERSONAL_TOKEN` — fine-grained PAT (Contents/Issues/PRs/Statuses R/W). Optional for a dry demo;
  required for live required-check / PR-comment / proxy-PR actions on the fork.

## Target repo
`Soham4001A/superset-cognition-demo` (fork of apache/superset) — carries the compliance kit + the
required Action; it's what Sentinel guards.

See **`PLAN.md`** for the full architecture, the federal framing, and the Nexus→Sentinel transposition.
