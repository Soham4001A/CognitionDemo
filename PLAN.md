# Sentinel — an autonomous, *required* compliance & docs gate on every PR, powered by Devin

> Take-home for Cognition (Devin). Target repo: `Soham4001A/superset-cognition-demo` (fork of apache/superset).
> Pitch audience: a federal-program VP of Engineering + senior ICs.

## 0. The one-liner (the differentiator)

Everyone builds *"Devin, go build ticket X → PR."* **Sentinel inverts it:** Devin **auto-attaches to every freshly-opened PR** as a **required, proactive reviewer** — it clones the repo in its own container, verifies documentation against the diff, runs a compliance scan suite, fixes what it can, opens its own reviewable proxy PR for the risky stuff, files a ticket + updates the SSP/POA&M, and **blocks merge** until it's satisfied and a human has signed off on security changes.

It is the pattern we already run internally (an orchestrator dispatches atomic tasks to an autonomous coding agent, tracks them in an engineering notebook, watches CI, and gates on compliance) **productized on Devin** for a regulated (federal/ATO) software shop.

Why it's *uniquely* a Devin play: a script/Dependabot can bump a version. It **cannot** read an ambiguous multi-file diff, decide the docs are now stale and rewrite them correctly, triage a SAST finding and fix it without breaking the app, or draft the POA&M narrative that maps the finding to an 800-53 control. That judgment work — done autonomously, as a *required gate*, on **every** PR — is the thing that isn't practical without an autonomous coding agent.

## 0.5 What shipped (two event-driven loops)

The build grew from one loop into two, both with Devin as the primitive:

1. **Issue remediation (the hook, Part 1):** a filed issue labeled `sentinel:remediate` → an `issues`
   webhook → a Devin session that fixes it in-container and opens a PR that `Closes #N`. Merge → the
   issue closes itself → the task resolves on the dashboard.
2. **PR compliance gate (the depth):** the loop in §1 below — Devin as a required reviewer on every PR.

Also shipped beyond the original plan: **Demo Control** (dashboard + `demo.sh`: reset/seed/remediate/
gate-pr for repeatable live demos), **fusion** of Devin's native PR review into the single verdict
comment, `devin/compliance` as the **sole required check** in the fork's branch protection, and a
`/how-it-works.html` walkthrough with an "Under the hood" technical breakdown. Proven live end-to-end:
issue → Devin → PR that `Closes #N` → merged → auto-closed; and PR → proxy PR → gate `success`.

## 1. The loop (per PR)

```
PR opened (feature → main)
   │  GitHub webhook: pull_request.opened
   ▼
ORCHESTRATOR
   ├─ set required check  devin/compliance = pending   (blocks merge)
   └─ POST /v1/sessions  (playbook prompt: repo, PR#, diff, policy, SSP/POAM paths, board API)
   ▼
DEVIN SESSION  (its own container)
   ├─ clone fork · compute diff vs main · lightweight bug-hunt
   ├─ DOCS: run Superset's own docs build/validation → verify docs vs the diff
   │        └─ stale? → commit doc fixes DIRECTLY to the feature branch      [no human gate]
   ├─ COMPLIANCE: run the suite (Trivy/Semgrep/Bandit/Gitleaks/Hadolint/kube-linter/licenses)
   │        └─ open PROXY PR  (sentinel/compliance-<pr#> → feature branch) with fixes
   │           orchestrator monitors proxy-PR CI ──► messages Devin to iterate until GREEN
   ├─ comment on the MAIN PR: human-digestible summary + evidence            [REQUIRED, always]
   ├─ create a ticket on the board (built-in, JIRA-equivalent API)
   └─ update + attach SSP + POA&M (append findings, map to controls)
   ▼
ORCHESTRATOR
   ├─ proxy PR requires HUMAN APPROVAL to merge (security change-control)
   └─ once Devin's comment is posted + any proxy PR merged → devin/compliance = passed → merge allowed
   ▼
DASHBOARD (live)  — instances · PRs + CI status · findings/POA&M burn-down · Devin's plans/insights · CHAT
```

### The "required, not additive" mechanism
- **Docs** → auto-committed to the feature branch. No gate (low-risk, high-toil).
- **Security fixes** → a **proxy PR** (Devin's changes get their *own* CI + a **required human approval** to merge). Federal change-control: you cannot cowboy-merge autonomous changes.
- **Every PR** → a **required check `devin/compliance`** that only passes once Devin has posted its digestible comment (and any proxy PR is resolved). So Devin is a **merge gate on everything humans ship**, not an opt-in helper.

## 2. Compliance scan suite (Nexus-derived; STIG/OpenSCAP/Nessus out, DAST deferred)

All **static** (no running app needed), run by Devin in-container. Each finding → a POA&M item mapped to a control.

| Scanner | Domain | 800-53 |
|---|---|---|
| Trivy (deps + image) | CVE / vuln | RA-5, SI-2 |
| Trivy SBOM (CycloneDX) | supply-chain provenance | SR-3, SR-4 |
| Semgrep | SAST (Py + TS) | SA-11, RA-5 |
| Bandit | Python SAST | SA-11 |
| Gitleaks | secrets | IA-5, SC-28 |
| Hadolint | Dockerfile hardening | CM-6, CM-7 |
| kube-linter | Helm/K8s hardening | CM-6 |
| license check (pip-licenses) | license compliance | SR-3 |
| docs-currency (Superset docs build) | config/doc baseline | CM-2/3, SA-5 |

Next-steps (video): ZAP/Nuclei DAST (needs a running Superset), Schemathesis API fuzz, OpenSCAP/STIG, real Nessus.

## 3. Components

1. **`superset-cognition-demo/`** — the fork (target). We add: scanner configs, a "compliance" GitHub Action (the required check surface), seed `compliance/SSP.md` + `compliance/POAM.md`, and a webhook → orchestrator.
2. **`sentinel/orchestrator/`** — FastAPI, Dockerized. The brain that does *no engineering*:
   - `POST /webhook/github` — `pull_request.opened` (+ `.synchronize`, CI `workflow_run`).
   - Devin client (`POST /v1/sessions`, `GET /v1/session/{id}`, `POST /v1/session/{id}/message`).
   - GitHub client (set commit status/required check, read PR CI, comment).
   - Poll loop (background) → session + PR + CI state.
   - Built-in **ticket board** API (JIRA-equivalent) + **SSP/POA&M** store.
   - Dashboard API + **chat relay** (state queries + steer a session).
   - State: SQLite (sessions, PRs, findings, tickets, POA&M items, plans).
3. **`sentinel/dashboard/`** — web UI: Devin instances, PRs in flight + CI status, findings/POA&M burn-down, Devin's plans/insights, **chat**.
4. **Built-in ticket board** — a JIRA-equivalent table + API in the orchestrator (Devin files tickets via it; the dashboard renders a Kanban). No external license.
5. **Devin playbook** — the prompt template encoding the per-PR workflow (the "job description" — Devin does the work).
6. **Compliance artifacts** — `SSP.md` + `POAM.md` seeded for the fork (Nexus-style), maintained by Devin per PR.

## 4. Observability (Part 3 — "how a VP/ISSO knows it's working")

Dashboard, in POA&M/MTTR language:
- **Devin instances** spawned (active/finished), per-PR.
- **PRs in flight** + their CI status (main PR + proxy PR).
- **Findings**: open vs. remediated, by control family; **POA&M burn-down** over time.
- **MTTR**: PR-opened → Devin-comment; finding → proxy-PR-green.
- **Success/failure** signals per session; Devin's **plan/insights** per PR.
- **Chat** transcript with the orchestrator.

## 5. Build phases (4 days; working-E2E > polish)

| Phase | Build fully (MVP, on-camera E2E) | Stub / narrate in video | Defer → next-steps |
|---|---|---|---|
| 0 Setup | ✅ done (fork, keys, Devin verified, workspace) | | |
| 1 Compliance baseline | seed SSP.md + POAM.md; scanner configs; "compliance" GH Action | full 800-53 catalog | OpenSCAP/STIG, SBOM signing |
| 2 Orchestrator | FastAPI: webhook → session → poll → required-check → state → dashboard API + chat relay | queueing/scale | multi-repo |
| 3 Devin playbook | full loop for **docs-staleness + 2-3 scanners** on one PR | full 8-scanner suite | deep bug-hunt |
| 4 Dashboard + chat | instances · PRs · CI · plans · chat | theming | multi-tenant |
| 5 Ticket board | built-in board + API (Devin files tickets) | | real JIRA/ServiceNow/MCP |
| 6 Docker + README + Loom | ✅ | | |

**MVP** = the whole loop on **one PR** — one docs fix + a couple compliance findings → proxy PR → required check → BLOCKER comment → ticket + POA&M update → all live on the dashboard, steerable via chat. Video narrates the full suite / SSP / multi-PR / air-gap vision.

## 6. Deliverables → take-home mapping

- **Part 1 (use case + issues):** the fork + **5 seeded, control-mapped Issues** (#5–#9) that Devin
  remediates via PRs that `Closes #N`.
- **Part 2 (event-driven automation):** three live triggers — `issues` (label → remediate),
  `pull_request` (opened → gate), `issue_comment` (@-mention) — each managing Devin sessions that
  produce real PRs / comments / tickets (observable outputs).
- **Part 3 (observability):** the dashboard — issue→PR→closed track, PR-gate track, findings-by-control
  burn-down, MTTR, audit trail; deep-links out to Devin per session.
- **Docker + public repo + README:** `Soham4001A/CognitionDemo`, one container, `docker compose up` (pinned deps).
- **Loom (<5 min):** What (backlog + compliance toil as event-driven Devin work) · How (live: label an
  issue → Devin fixes → PR closes it; then the PR gate) · Why (Devin's judgment, event-driven, as a
  required gate) · When (DAST, real JIRA/ServiceNow, air-gapped enclave, multi-repo, policy-as-code).

## 7. Risks / unknowns → de-risk

- **Devin session limits / ACU** on a long CI-monitor loop → split: Devin *fixes*, orchestrator *monitors* CI + messages Devin to iterate. Bounded rounds.
- **Devin "auto-attach"** is *our* orchestration (GH webhook → session), not a Devin-native watch — articulate that honestly; it's the point (event-driven).
- **Superset is huge** → scope Devin's diff-scoped work + shallow clones; cap scan targets to changed paths where sensible.
- **Public demo ≠ real enclave** → narrate the air-gapped/controlled-deployment mapping (Devin-in-enclave, evidence to the ATO package) in the video.
- **Non-determinism of an agent demo** → pre-stage a known PR that triggers a known docs-stale + finding, so the live demo is reproducible.

## 8. Packaging & reproducibility — one-click demo (first-class requirement)

Solution repo: **`Soham4001A/CognitionDemo`** (product = **Sentinel**). Must run on a *fresh laptop* with no tribal knowledge. Deliver:

- **`setup.sh`** — idempotent bootstrap: checks Docker + toolchain, copies `.env.example`→`.env` (prompts for `DEVIN_API_KEY` + `GH_PERSONAL_TOKEN`), builds images, runs a **preflight** (Devin `GET /v1/sessions` 200, GitHub token scopes OK), prints next steps. Re-runnable.
- **`docker compose up`** — brings up orchestrator + dashboard (+ built-in board). Zero host-specific paths.
- **One-click demo** — a **"Run Demo" button in the dashboard** (and a `demo.sh` equivalent) that **opens a pre-staged PR** on the fork (a known change that deterministically triggers a docs-stale + ≥1 compliance finding), so the full loop plays out live on the dashboard without hand-driving. Reproducible for the Loom.
- **`AGENT_ONBOARD.md`** — a long, self-contained context prompt to hand a **fresh agent** (or paste when SSH'd into another machine): what Sentinel is, the architecture, how to run it, the demo, and how to extend it. This is the "give a fresh agent everything" artifact the operator asked for.
- **Portability** — everything in Docker + `.env`; the only inputs are the two keys. Optional: a `Makefile` (`make setup`, `make demo`, `make up`) as the friendly surface.

Acceptance: on a clean machine, `./setup.sh && docker compose up` + one button-click reproduces the end-to-end demo.

## 9. Nexus → Sentinel transposition (the pitch spine)

| Nexus (how we work today) | Sentinel (the product) |
|---|---|
| Claude Code as the autonomous coder | Devin as the autonomous coder |
| Human orchestrator dispatches atomic tasks | Orchestrator service dispatches Devin sessions on PR events |
| Engineering notebook / tracker | Dashboard + built-in ticket board + state |
| "Watch CI to green" discipline | Orchestrator monitors proxy-PR CI, iterates Devin to green |
| RULE #1 / gates / POA&M / IATT / STIG | Required check + proxy-PR approval + SSP/POA&M + control-mapped findings |
| Chatting with the orchestrator (me) | Chat interface to the Sentinel orchestrator |
