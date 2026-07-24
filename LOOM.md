# Sentinel — Loom script (≤5 min)

Audience: a **federal-program VP of Engineering + senior ICs** evaluating Devin. Keep it tight; show
the loop working. Have the dashboard (`http://localhost:8080`) and the fork PR page open in tabs.

## 0. Cold open (15s)
"Every Devin demo you've seen is *'Devin, go build this ticket.'* I built the version a regulated
engineering org actually needs: **Devin as an event-driven teammate** that remediates filed issues *and*
stands as a required compliance gate on every PR — autonomously, with an audit trail."

## 1. WHAT — the problem (40s)
- In an ATO/federal program, backlog issues (vuln findings, dependency bumps, hardening gaps) pile up,
  and every PR must satisfy docs currency + security scans where each finding is a POA&M item tied to an
  800-53 control. Today that's manual toil that either slows delivery or gets skipped.
- "Sentinel makes **Devin** the primitive that clears both — triggered by events, producing real PRs and
  audit evidence." (Show the fork's **Issues** list + `how-it-works.html` for one beat.)

## 2. HOW — demo, issues as the hook then the gate as depth (2m40s)

**Act 1 — issue remediation (the literal ask):**
1. **Show the Issues** I filed in the fork, each mapped to a control (SR-3 headers, RA-5 version pinning,
   CM-6 Dockerfile…). "These are the issues I selected to remediate."
2. **Label one `sentinel:remediate`.** "That's the only human action." The `issues` webhook fires →
   the dashboard's **issue-remediation track** shows a Devin session appear.
3. **Open the session URL:** Devin clones, fixes in its own container, and opens a PR that **`Closes #N`**.
   Merge it → the issue **closes itself**, the dashboard flips it to remediated, MTTR ticks. "Issue →
   Devin → PR → closed. The orchestrator did zero engineering — `playbook.py` is the job description."

**Act 2 — the compliance gate (the depth):**
4. **Open a PR** on the fork. Devin auto-attaches as a **required reviewer**: `devin/compliance` goes
   *pending*, then docs are fixed+committed to the branch (low-risk, no gate), the scan suite runs, and a
   **proxy PR** carries the security fix. "Docs auto-applied; the security fix goes through its **own
   reviewable PR a human must approve** — federal change-control. Merge blocked until then."
5. **One unified comment:** Devin's built-in review is **fused in** — a single verdict comment mapping
   every finding to its 800-53 control, not two competing bots. Show the **findings-by-control burn-down**
   and the **POA&M rows** Devin appended. "That's ATO evidence, generated automatically."
6. **Chat / steer** (optional): ask "what's open?", then steer a live session by id. "A VP talks to the
   orchestrator directly — not just tagging Devin in git."

## 3. WHY — uniquely Devin (45s)
"A script or Dependabot can bump a version. It **can't** read an ambiguous issue and fix it across the
codebase, decide docs are now wrong and rewrite them, triage a SAST finding without breaking the app, or
draft the POA&M narrative. That judgment — event-driven, as a required gate — isn't practical without an
autonomous coding agent. That's the whole thesis."

## 4. WHEN — next steps (30s)
"In a real engagement: add DAST once the app is stood up, swap the built-in board for JIRA/ServiceNow,
run Devin **inside the customer's enclave** with evidence flowing to the ATO package, make
`devin/compliance` a required check across every repo, and layer policy-as-code. The pattern generalizes
to any regulated codebase."

## Close (10s)
"Two event-driven loops, Devin as the primitive in both, and a dashboard that answers *'how do I know
this is working?'* Repo + one-click setup in the description. Thanks."

---
**Recording tips:** pre-run `./setup.sh` + `docker compose up`; have the fork **Issues** + dashboard +
`/how-it-works.html` open in tabs. A live Devin session takes minutes — pre-run one issue + one PR
beforehand and narrate the already-populated dashboard, then trigger a fresh one live to show the webhook.
