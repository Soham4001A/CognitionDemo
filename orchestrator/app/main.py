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
import os
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .devin import DevinClient
from .github_client import GitHubClient
from .playbook import build_playbook
from .poller import poll_loop
from .state import Store

REPO = os.environ.get("TARGET_REPO", "Soham4001A/superset-cognition-demo")
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


@app.post("/webhook/github")
async def github_webhook(request: Request):
    event = request.headers.get("X-GitHub-Event", "")
    payload = await request.json()
    if event == "pull_request" and payload.get("action") in ("opened", "reopened", "ready_for_review"):
        pr = payload["pull_request"]
        return attach_devin(
            pr=pr["number"], title=pr.get("title", ""),
            base=pr["base"]["ref"], head=pr["head"]["ref"], sha=pr["head"]["sha"],
        )
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
    store.add_ticket(tid, pr, body.get("title", "finding"), control, sev, "open",
                     f"{PUBLIC_URL}/#ticket-{tid}")
    store.log("ticket", f"{tid} [{control}/{sev}] {body.get('title','')}", pr)
    return {"id": tid}


@app.get("/api/state")
def state():
    return {
        "target": REPO,
        "reviews": store.list_reviews(),
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
