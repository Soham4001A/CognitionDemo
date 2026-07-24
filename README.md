# Sentinel

**Event-driven remediation & a required compliance gate — powered by [Devin](https://devin.ai).**

Two event-driven loops, both with Devin as the primitive that does the actual engineering:

1. **Issue remediation (the hook).** File a GitHub issue labeled `sentinel:remediate` → an `issues`
   webhook dispatches a Devin session that clones the repo, fixes the issue in its own container, and
   opens a PR that **`Closes #N`**. Merge it and the issue closes itself.
2. **PR compliance gate (the depth).** When any PR opens, Devin auto-attaches as a **required reviewer**:
   verifies docs against the diff, runs a control-mapped scan suite, fixes what it can, opens a reviewable
   **proxy PR** for the risky changes, files tickets, updates the **SSP/POA&M**, and **blocks merge** via a
   required `devin/compliance` check until a human approves the security changes.

The orchestrator does **zero engineering** — it routes events, sets the gate, and observes. Devin clones,
fixes, and opens PRs. It's the orchestration pattern a regulated (federal/ATO) shop runs by hand —
productized on Devin, with a leader's dashboard for observability.

## Quickstart

```bash
./setup.sh          # checks Docker, fills .env (DEVIN_API_KEY, GH_PERSONAL_TOKEN), preflights, builds
docker compose up   # (or: make up)  → http://localhost:8080   (also /how-it-works.html)
```

One container (`sentinel`) serves the API **and** the dashboard on `:8080`. Two ways to demo each loop:

```bash
# Issue remediation:  label an issue sentinel:remediate  (true webhook)
#                     …or headless:  curl -X POST localhost:8080/api/demo/remediate -d '{"issue":6}'
# PR compliance gate:  open a PR      (true webhook)
#                     …or dashboard "Run PR review" / curl -X POST localhost:8080/api/demo/run -d '{"pr":3}'
```

## Triggers (all three, live)

| Trigger | Event | Loop |
|---|---|---|
| **Issue labeled** `sentinel:remediate` | `issues` webhook | remediation → PR that `Closes #N` |
| **PR opened** | `pull_request` webhook | compliance gate → proxy PR |
| **@sentinel / @devin** in a PR comment | `issue_comment` webhook | compliance gate |
| **Chat** ("review PR 3") | dashboard `/api/chat` | either, + steer a live session by id |

Self-recursion is guarded: `sentinel/*` branches and Devin-authored PRs never trigger a new review.

## The two loops

```
ISSUE:  issue labeled sentinel:remediate → Devin session → fix in-container
        → PR that `Closes #N` → (human merges) → issue auto-closes → task resolved

PR:     PR opened → required check devin/compliance = pending → Devin session
        → docs fixed+committed to the branch (low-risk, no gate)
        → scan suite → PROXY PR (human-approve to merge) → ONE unified review comment
        → tickets + SSP/POA&M (finding → 800-53 control) → gate resolves on merge
```

Docs auto-commit (low-risk); security fixes go through a proxy PR (human approval required); every PR
gets a required `devin/compliance` status. Devin's built-in PR reviewer is **fused in** — Sentinel folds
its findings into one unified verdict comment rather than leaving a second advisory review.

## Observability (Part 3 — "how would a leader know this is working?")

The dashboard (`localhost:8080`) is the compliance control plane — it deep-links out to Devin for any
single session rather than reproducing it: program-posture tiles (issues remediated, PRs gated, findings,
active sessions, **MTTR**), the issue→session→PR→closed track, the PR-review gate track, a
**findings-by-800-53-control** burn-down, a ticket board, an event/audit timeline, and chat to steer Devin.

## Compliance suite (control-mapped, static)

Trivy (RA-5/SI-2) · Trivy-SBOM (SR-3/4) · Semgrep + Bandit (SA-11) · Gitleaks (IA-5/SC-28) ·
Hadolint + kube-linter (CM-6/7) · license check (SR-3) · docs-currency (CM-2/3, SA-5).
Each finding becomes a POA&M item tied to its control. (DAST/OpenSCAP/Nessus → next-steps.)

## Layout

| Path | What |
|---|---|
| `orchestrator/app/playbook.py` | **core IP** — the per-PR review + per-issue remediation Devin job descriptions |
| `orchestrator/app/main.py` | FastAPI: `issues`/`pull_request`/`issue_comment` webhooks · demo · tickets · state · chat |
| `orchestrator/app/poller.py` | tracks Devin sessions → drives the gate + issue-remediation to resolution |
| `orchestrator/app/{devin,github_client,state}.py` | Devin client · GitHub client · SQLite state |
| `orchestrator/static/index.html` | the compliance control-plane dashboard |
| `orchestrator/static/how-it-works.html` | visual walkthrough (served at `/how-it-works.html`) |
| `compliance/` | SSP + POA&M (Devin-maintained) · `scanners/` · `compliance.yml` Action |
| `PLAN.md` · `TRACKER.md` · `AGENT_ONBOARD.md` | architecture · build notebook · fresh-agent context |

## Config (`.env`, gitignored — see `.env.example`)
- `DEVIN_API_KEY` — `apk_user_…` (Devin → Settings → API Keys).
- `GH_PERSONAL_TOKEN` — fine-grained PAT (Contents/Issues/PRs/Statuses/Administration R/W on the fork).
- `PUBLIC_URL` — public base (e.g. a `cloudflared` tunnel) so GitHub webhooks reach the orchestrator.

## Target repo
`Soham4001A/superset-cognition-demo` (fork of apache/superset) — carries the compliance kit, the required
`devin/compliance` branch-protection check, and the seeded issues (`sentinel:remediate`) Sentinel remediates.

See **`PLAN.md`** for the full architecture and federal framing, and `/how-it-works.html` for the visual walkthrough.
