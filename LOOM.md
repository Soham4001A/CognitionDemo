# Sentinel — Loom script (≤5 min)

Audience: a **federal-program VP of Engineering + senior ICs** evaluating Devin. Keep it tight; show
the loop working. Have the dashboard (`http://localhost:8080`) and the fork PR page open in tabs.

## 0. Cold open (15s)
"Every Devin demo you've seen is *'Devin, go build this ticket.'* I built the opposite: **Devin as a
required gate on every PR** — it reviews, fixes docs, runs compliance, and blocks merge, autonomously.
For a regulated shop, that's the difference between a helper and a control."

## 1. WHAT — the problem (45s)
- In an ATO/federal program, every PR has to satisfy docs currency + a stack of security/compliance
  scans, and every finding is a POA&M item tied to an 800-53 control. Today that's manual toil that
  either slows delivery or gets skipped.
- "Sentinel makes Devin a **required, autonomous reviewer** on every PR — the toil clears itself, with
  an audit trail." (Show `PLAN.md` §0 + the control-mapped scanner table for one beat.)

## 2. HOW — demo the loop (2m30s)
1. **Open the PR** on the fork (`demo/sentinel-showcase`): an undocumented feature flag + an unhardened
   Dockerfile. "A normal contributor PR."
2. **Dashboard → "▶ Run Demo"** (or it fires on the webhook). "The orchestrator sets a required
   `devin/compliance` check to *pending* and dispatches a Devin session — watch it appear."
3. **Show Devin working** (open the session URL): clone → diff → docs build → scan suite in its own
   container. "The orchestrator does zero engineering — this playbook (`playbook.py`) is the job
   description; **Devin** does the work."
4. **Outputs land on the dashboard live:** the instance, the plan, findings-by-control burn-down, the
   ticket board filling, MTTR ticking. On the PR: Devin's **required review comment**, a **docs commit
   on the feature branch**, and a **proxy PR** with the Hadolint fix. "Docs auto-applied — low risk.
   Security fix goes through its **own reviewable PR that a human must approve** — federal change-control."
5. **Chat**: type a question ("what's open?") and then steer a session (`@<session_id> also check the
   helm chart`). "A VP or IC talks to the orchestrator directly — not just tagging Devin in git."
6. **SSP/POA&M**: show the POA&M rows Devin appended, each mapped to a control. "That's ATO evidence,
   generated automatically."

## 3. WHY — uniquely Devin (45s)
"A script or Dependabot can bump a version. It **can't** read an ambiguous diff, decide the docs are
now wrong and rewrite them, triage a SAST finding and fix it without breaking the app, or draft the
POA&M narrative. That judgment — done autonomously, as a **required gate on every PR** — isn't practical
without an autonomous coding agent. That's the whole thesis."

## 4. WHEN — next steps (30s)
"In a real engagement: add DAST once the app is stood up, swap the built-in board for JIRA/ServiceNow,
run Devin **inside the customer's enclave** with evidence flowing to the ATO package, make these
required checks in branch protection across every repo, and layer policy-as-code. The pattern
generalizes to any regulated codebase."

## Close (10s)
"Same orchestration discipline a senior engineer runs by hand — productized on Devin. Repo + one-click
setup in the description. Thanks."

---
**Recording tips:** pre-run `./setup.sh` + `docker compose up`; pre-open the PR; if a live Devin session
is too slow for 5 min, run it once beforehand and narrate the already-populated dashboard + PR.
