"""Sentinel orchestrator (FastAPI). Does NO engineering — it routes events, sets the required
check, dispatches + polls Devin, relays chat. Devin does the work.

Routes:
  POST /webhook/github  - pull_request.opened  -> attach Devin (the core loop kickoff)
  POST /api/demo/run    - one-click demo: synthesize a pull_request.opened for a given PR
  POST /api/tickets     - Devin files a board ticket
  GET  /api/state       - dashboard payload (reviews, findings, tickets, events, metrics, chat)
  POST /api/chat        - chat: query state OR steer a live session (POST /v1/session/{id}/message)
  GET  /healthz
"""
from __future__ import annotations

import asyncio
import base64
import os
import re
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .devin import DevinClient
from .github_client import GitHubClient
from .playbook import build_playbook, build_remediation_playbook
from .poller import poll_loop
from .state import Store

REMEDIATE_LABEL = "sentinel:remediate"

REPO = os.environ.get("TARGET_REPO", "Soham4001A/superset-cognition-demo")
REPO_DEFAULT_BASE = os.environ.get("TARGET_BASE", "master")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:8080")

app = FastAPI(title="Sentinel Orchestrator")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

store = Store()
devin = DevinClient()
gh: GitHubClient | None = GitHubClient(REPO) if os.environ.get("GH_PERSONAL_TOKEN") else None


@app.on_event("startup")
async def _startup():
    asyncio.create_task(poll_loop(store, devin, gh))
    store.log("startup", f"Sentinel up · target={REPO} · github={'on' if gh else 'off (no PAT)'}")


@app.get("/healthz")
def healthz():
    return {"ok": True, "target": REPO, "github": bool(gh)}


def attach_devin(pr: int, title: str, base: str, head: str, sha: str) -> dict[str, Any]:
    """The core loop kickoff: set required check pending, dispatch a Devin session with the playbook."""
    if gh and sha:
        try:
            gh.set_required_check(sha, "pending", "Sentinel reviewing — docs + compliance", PUBLIC_URL)
        except Exception as e:  # non-fatal in demo
            store.log("warn", f"set_required_check failed: {e}", pr)

    prompt = build_playbook({
        "repo": REPO, "pr": pr, "title": title, "base": base, "head": head, "sha": sha,
        "board_api": f"{PUBLIC_URL}/api/tickets",
    })
    session = devin.create_session(prompt, title=f"Sentinel · PR #{pr} · {REPO}",
                                   tags=["sentinel", "compliance", f"pr-{pr}"])
    sid = session.get("session_id")
    store.upsert_review(pr, repo=REPO, title=title, base_branch=base, head_branch=head, head_sha=sha,
                        session_id=sid, session_url=session.get("url"), phase="running",
                        check_state="pending")
    store.log("attach", f"Devin session {sid} attached to PR #{pr}", pr)
    return {"pr": pr, "session_id": sid, "session_url": session.get("url")}


def attach_by_number(pr_number: int) -> dict[str, Any]:
    """Attach by PR number (used by tagging + chat). Fetches the PR from GitHub, then dispatches."""
    if not gh:
        return {"error": "GH_PERSONAL_TOKEN required to attach by PR number"}
    p = gh.get_pr(pr_number)
    return attach_devin(pr_number, p.get("title", ""), p["base"]["ref"], p["head"]["ref"],
                        p["head"]["sha"])


def dispatch_remediation(issue: int, title: str, body: str, base: str = "master") -> dict[str, Any]:
    """Issue-triggered loop: a filed issue -> a Devin session that fixes it and opens a PR that
    `Closes #issue`. Records a task the poller tracks through to the issue being closed."""
    if store.get_task(issue) and store.get_task(issue).get("phase") not in (None, "error"):
        return {"skipped": "already dispatched", "issue": issue}
    prompt = build_remediation_playbook({
        "repo": REPO, "issue": issue, "title": title, "body": body, "base": base,
        "board_api": f"{PUBLIC_URL}/api/tickets",
    })
    session = devin.create_session(prompt, title=f"Sentinel · remediate #{issue} · {REPO}",
                                   tags=["sentinel", "remediation", f"issue-{issue}"])
    sid = session.get("session_id")
    store.upsert_task(issue, title=title, session_id=sid, session_url=session.get("url"),
                      phase="running")
    store.log("remediate", f"Devin session {sid} dispatched to fix issue #{issue}", issue)
    return {"issue": issue, "session_id": sid, "session_url": session.get("url")}


def _has_remediate_label(issue: dict[str, Any]) -> bool:
    return any((lbl.get("name") == REMEDIATE_LABEL) for lbl in (issue.get("labels") or []))


@app.post("/webhook/github")
async def github_webhook(request: Request):
    event = request.headers.get("X-GitHub-Event", "")
    payload = await request.json()
    # 1) automatic: a PR is opened
    if event == "pull_request" and payload.get("action") in ("opened", "reopened", "ready_for_review"):
        pr = payload["pull_request"]
        # BUG A fix — never review our OWN proxy PRs (sentinel/* branch) or Devin-authored PRs,
        # or we recurse (proxy PR → new review → new proxy PR …) and burn ACU.
        head_ref = pr["head"]["ref"]
        author = (pr.get("user") or {}).get("login", "").lower()
        if head_ref.startswith("sentinel/") or "devin" in author or "sentinel" in author:
            store.log("skip", f"ignored self/agent PR #{pr['number']} ({head_ref} by {author})", pr["number"])
            return {"skipped": "self/agent PR", "pr": pr["number"], "head": head_ref}
        return attach_devin(
            pr=pr["number"], title=pr.get("title", ""),
            base=pr["base"]["ref"], head=head_ref, sha=pr["head"]["sha"],
        )
    # 1b) automatic: an issue is filed/labeled for remediation (the Part-1 loop)
    if event == "issues" and payload.get("action") in ("opened", "labeled", "reopened"):
        issue = payload.get("issue") or {}
        if issue.get("number") and _has_remediate_label(issue):
            return dispatch_remediation(issue["number"], issue.get("title", ""),
                                        issue.get("body") or "", REPO_DEFAULT_BASE)
        return {"ignored": "issue without sentinel:remediate label", "issue": issue.get("number")}
    # 2) tagging: someone @-mentions Sentinel/Devin in a PR comment
    if event == "issue_comment" and payload.get("action") == "created":
        body = ((payload.get("comment") or {}).get("body") or "").lower()
        issue = payload.get("issue") or {}
        if issue.get("pull_request") and any(m in body for m in ("@sentinel", "@devin")):
            store.log("trigger", f"tagged on PR #{issue['number']}", issue["number"])
            return attach_by_number(issue["number"])
    return {"ignored": event, "action": payload.get("action")}


@app.post("/api/demo/run")
async def demo_run(body: dict[str, Any]):
    """One-click demo. If a PR number is given, read it from GitHub and attach; else attach a
    synthetic PR context so the loop runs even without a live PR/token."""
    pr = int(body.get("pr", 0))
    if gh and pr:
        p = gh.get_pr(pr)
        return attach_devin(pr, p.get("title", ""), p["base"]["ref"], p["head"]["ref"], p["head"]["sha"])
    # fallback synthetic (no token): still spawns a real Devin session on the loop
    return attach_devin(pr or 1, body.get("title", "demo PR"),
                        body.get("base", "master"), body.get("head", "demo/feature"), body.get("sha", ""))


@app.post("/api/tickets")
async def create_ticket(body: dict[str, Any]):
    pr = int(body.get("pr", 0))
    control = body.get("control", "RA-5")
    sev = body.get("severity", "medium")
    tid = f"SENT-{pr}-{len(store.list_tickets())+1:03d}"
    title = body.get("title", "finding")
    store.add_ticket(tid, pr, title, control, sev, "open", f"{PUBLIC_URL}/#ticket-{tid}")
    # BUG B fix — mirror the ticket into findings so the dashboard burn-down / by-control /
    # by-severity actually reflect Devin's work (Devin files tickets, not raw findings).
    store.add_findings(pr, [{
        "id": tid, "scanner": body.get("scanner", "sentinel"), "control": control,
        "severity": sev, "message": title, "fixable": body.get("fixed") is not None,
        "status": "remediated" if body.get("fixed") else "open",
    }])
    store.log("ticket", f"{tid} [{control}/{sev}] {title}", pr)
    return {"id": tid}


# The control-mapped issues the demo remediates — seeded so a live run is repeatable.
SEED_ISSUES = [
    {"title": "[SR-3] Add Apache license headers to compliance scanner scripts",
     "body": "`compliance/scanners/normalize.py` and `compliance/scanners/run_scans.sh` ship without the "
             "standard Apache Software Foundation license header carried by the rest of the tree — a "
             "software-supply-chain / provenance gap (NIST 800-53 **SR-3**, SA-5).\n\n**Remediation:** "
             "prepend the standard ASF header to both files. No logic changes."},
    {"title": "[RA-5/SI-2] Pin scanner tool versions in run_scans.sh",
     "body": "`compliance/scanners/run_scans.sh` installs tooling unpinned (`pip install -q semgrep`, "
             "`bandit`, `pip-licenses`) — non-reproducible and a supply-chain risk (NIST 800-53 "
             "**RA-5 / SI-2 / SR-3**).\n\n**Remediation:** pin each scanner to a known-good version."},
    {"title": "[CM-6/CM-7] Harden dockerize.Dockerfile against Hadolint findings",
     "body": "`dockerize.Dockerfile` should be reviewed against Hadolint (NIST 800-53 **CM-6 / CM-7**): "
             "pin the base tag, add `--no-install-recommends` + version pins, clean apt lists in-layer, "
             "run non-root where feasible.\n\n**Remediation:** apply hardening; keep it functional."},
    {"title": "[SA-11] Harden JSON/subprocess handling in normalize.py",
     "body": "`compliance/scanners/normalize.py` must never crash the gate on malformed/empty scanner "
             "JSON (NIST 800-53 **SA-11**). Review for bare `except:`, missing empty-input guards.\n\n"
             "**Remediation:** tighten exception handling + guards so a bad raw file degrades gracefully."},
    {"title": "[IA-5/SC-28] .gitignore does not exclude scanner outputs",
     "body": "Scan runs write `sentinel-scan/` (raw JSON, SBOM, findings) which can contain paths and "
             "matched secret material — must not be committed (NIST 800-53 **IA-5 / SC-28**).\n\n"
             "**Remediation:** add `sentinel-scan/` and `*.sarif` to `.gitignore`."},
]

_FLAWED_DOCKERFILE = (
    "# demo.live.Dockerfile — deliberately flawed for the Sentinel PR-gate demo\n"
    "FROM python:latest\n"                       # unpinned base (Hadolint DL3007)
    "RUN apt-get update && apt-get install -y curl\n"  # no --no-install-recommends / no cleanup
    "ENV SENTINEL_LIVE_DEMO_FLAG=1\n"            # undocumented flag → docs drift
    "COPY . /app\n"
    "CMD python /app/main.py\n"
)


@app.post("/api/demo/reset")
def demo_reset(body: dict[str, Any] | None = None):
    """Clean the fork to a repeatable demo baseline: close open PRs, delete sentinel/* branches,
    reopen + unlabel the seed issues, and wipe orchestrator state. Scoped to demo artifacts only."""
    summary = {"closed_prs": [], "deleted_branches": [], "reopened_issues": [], "unlabeled_issues": []}
    if gh:
        for p in gh.list_pulls("open"):
            try:
                gh.close_pull(p["number"]); summary["closed_prs"].append(p["number"])
            except Exception as e:
                store.log("warn", f"reset: close PR #{p['number']} failed: {e}")
        for b in gh.list_branches():
            name = b.get("name", "")
            if name.startswith("sentinel/") or name.startswith("demo/live"):
                try:
                    gh.delete_branch(name); summary["deleted_branches"].append(name)
                except Exception as e:
                    store.log("warn", f"reset: delete branch {name} failed: {e}")
        for i in gh.list_issues_only("all"):
            n = i["number"]
            if i.get("state") == "closed":
                try:
                    gh.set_issue_state(n, "open"); summary["reopened_issues"].append(n)
                except Exception:
                    pass
            if any(l.get("name") == REMEDIATE_LABEL for l in (i.get("labels") or [])):
                try:
                    gh.set_issue_labels(n, []); summary["unlabeled_issues"].append(n)
                except Exception:
                    pass
    store.reset()
    store.log("reset", f"demo reset — closed {len(summary['closed_prs'])} PR(s), "
                       f"deleted {len(summary['deleted_branches'])} branch(es)")
    return {"ok": True, **summary}


@app.post("/api/demo/seed")
def demo_seed(body: dict[str, Any] | None = None):
    """Ensure the control-mapped seed issues exist (open + unlabeled) so a live remediation is repeatable."""
    if not gh:
        return {"error": "GH_PERSONAL_TOKEN required"}
    existing = {i["title"] for i in gh.list_issues_only("all")}
    created = []
    for spec in SEED_ISSUES:
        if spec["title"] not in existing:
            r = gh.create_issue(spec["title"], spec["body"], [])
            created.append(r["number"])
    store.log("seed", f"seed issues ensured ({len(created)} created)")
    return {"ok": True, "created": created, "total_seed": len(SEED_ISSUES)}


@app.post("/api/demo/seed_pr")
def demo_seed_pr(body: dict[str, Any] | None = None):
    """Recreate a live PR-gate demo: a fresh branch off the base with a deliberately-flawed Dockerfile
    (unpinned base, apt hygiene, an undocumented flag) → opens a PR that triggers Devin's compliance gate."""
    if not gh:
        return {"error": "GH_PERSONAL_TOKEN required"}
    branch = "demo/live-review"
    try:
        gh.delete_branch(branch)  # start fresh if it lingers
    except Exception:
        pass
    base_sha = gh.default_branch_sha(REPO_DEFAULT_BASE)
    gh.create_branch(branch, base_sha)
    gh.put_file("demo.live.Dockerfile", branch,
                base64.b64encode(_FLAWED_DOCKERFILE.encode()).decode(),
                "demo: add live-review Dockerfile (deliberately flawed)")
    pr = gh.open_pull("Add live demo service (compliance gate showcase)", branch, REPO_DEFAULT_BASE,
                      "Adds a demo service Dockerfile with an undocumented flag — for the Sentinel "
                      "compliance-gate live demo. Devin should flag the hardening + docs drift.")
    store.log("seed", f"seed PR #{pr['number']} opened on {branch}")
    return {"ok": True, "pr": pr["number"], "url": pr.get("html_url")}


@app.post("/api/demo/remediate")
async def demo_remediate(body: dict[str, Any]):
    """One-click issue-remediation demo. Give an existing issue number (reads it from GitHub) or a
    title+body to synthesize one; dispatches a Devin remediation session either way."""
    issue = int(body.get("issue", 0))
    if gh and issue:
        i = gh.get_issue(issue)
        return dispatch_remediation(issue, i.get("title", ""), i.get("body") or "", REPO_DEFAULT_BASE)
    return dispatch_remediation(issue or 1, body.get("title", "demo issue"),
                                body.get("body", ""), REPO_DEFAULT_BASE)


@app.get("/api/state")
def state():
    return {
        "target": REPO,
        "reviews": store.list_reviews(),
        "tasks": store.list_tasks(),
        "findings": store.list_findings(),
        "tickets": store.list_tickets(),
        "events": store.list_events(),
        "metrics": store.metrics(),
        "chat": store.list_chat(),
    }


@app.post("/api/chat")
async def chat(body: dict[str, Any]):
    msg = (body.get("message") or "").strip()
    session_id = body.get("session_id")
    store.add_chat("user", msg, session_id)
    # chat-initiated review: "review PR 123" / "@sentinel review 123"
    m = re.search(r"review\s+(?:pr\s*)?#?(\d+)", msg, re.I)
    if m and not session_id:
        res = attach_by_number(int(m.group(1)))
        reply = (f"Attaching Devin to PR #{m.group(1)} — session {res.get('session_id', '?')}."
                 if "session_id" in res else res.get("error", "attach failed"))
        store.add_chat("sentinel", reply)
        return {"reply": reply, "attach": res}
    # steer a live session if one is targeted, else answer from state
    if session_id:
        try:
            devin.send_message(session_id, msg)
            reply = f"Relayed to Devin session {session_id}."
        except Exception as e:
            reply = f"Could not reach session {session_id}: {e}"
    else:
        m = store.metrics()
        reply = (f"{m['reviews']} PR review(s), {m['active']} active. "
                 f"{m['findings_open']} open finding(s), {m['findings_remediated']} remediated. "
                 f"Target: {REPO}. Ask me to steer a session by passing its session_id.")
    store.add_chat("sentinel", reply, session_id)
    return {"reply": reply}


# serve the dashboard (single container). Mounted LAST so the /api + /webhook routes win.
app.mount("/", StaticFiles(directory="static", html=True), name="dashboard")
