"""Background poll loop: track active Devin sessions, ingest their structured output, and drive the
required `devin/compliance` check so the gate VISIBLY resolves:

  running                      -> pending  ("Sentinel reviewing")
  review done + proxy PR open  -> pending  ("awaiting proxy PR #N approval")   [human gate]
  review done + proxy merged   -> success  ("remediations merged")            [resolved]
  review done + no proxy PR    -> success  ("no remediation needed")          [resolved]
  review done + proxy closed   -> failure  ("proxy PR closed unmerged")       [resolved]

Devin does the fixing; we observe + gate.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

POLL_SECS = 15


async def poll_loop(store, devin, gh) -> None:
    while True:
        try:
            for r in store.list_reviews():
                if r.get("phase") == "resolved":
                    continue  # terminal — check is final
                await _tick(store, devin, gh, r)
        except Exception as e:
            store.log("error", f"poller: {e}")
        await asyncio.sleep(POLL_SECS)


async def _tick(store, devin, gh, r: dict[str, Any]) -> None:
    sid, pr = r.get("session_id"), r["pr"]
    if not sid:
        return
    s = await asyncio.to_thread(devin.get_session, sid)
    phase = devin.phase(s.get("status_enum"))
    structured = s.get("structured_output") or {}
    fields: dict[str, Any] = {"phase": phase}

    plan = _plan_text(s)
    if plan:
        fields["plan"] = plan
    if structured:
        fields["structured"] = structured
        for i, f in enumerate(structured.get("findings") or []):
            store.add_findings(pr, [{
                "id": f.get("id", f"F{i}"), "scanner": f.get("scanner"), "control": f.get("control"),
                "severity": f.get("severity", "medium"), "message": f.get("message", ""),
                "fixable": f.get("fixed") is not None,
                "status": "remediated" if f.get("fixed") else "open",
            }])
        if structured.get("proxy_pr") and not r.get("proxy_pr"):
            fields["proxy_pr"] = _pr_number(structured["proxy_pr"])

    # First time the review completes → record MTTR + start gate resolution.
    if phase == "done" and not r.get("commented"):
        fields["commented"] = time.time()
        store.log("reviewed", f"Devin finished review of PR #{pr}", pr)

    # Drive the required check whenever the review is (or has been) done.
    if phase == "done" or r.get("commented"):
        proxy = fields.get("proxy_pr") or r.get("proxy_pr")
        state, desc, resolved = await _gate(gh, proxy)
        fields["check_state"] = state
        if resolved:
            fields["phase"] = "resolved"
        if gh and r.get("head_sha"):
            try:
                await asyncio.to_thread(gh.set_required_check, r["head_sha"], state, desc,
                                        r.get("session_url", ""))
            except Exception as e:
                store.log("warn", f"set check {state} failed: {e}", pr)

    store.upsert_review(pr, **fields)


async def _gate(gh, proxy_pr) -> tuple[str, str, bool]:
    """Return (commit-status state, description, resolved?) for the required check."""
    if not proxy_pr:
        return "success", "Sentinel review complete — no remediation required", True
    if not gh:
        return "pending", f"review complete — proxy PR #{proxy_pr} awaiting approval", False
    try:
        p = await asyncio.to_thread(gh.get_pr, int(proxy_pr))
    except Exception:
        return "pending", f"review complete — proxy PR #{proxy_pr} awaiting approval", False
    if p.get("merged"):
        return "success", f"remediations merged (proxy PR #{proxy_pr})", True
    if p.get("state") == "closed":
        return "failure", f"proxy PR #{proxy_pr} closed unmerged — findings unresolved", True
    return "pending", f"review complete — proxy PR #{proxy_pr} awaiting human approval", False


def _plan_text(s: dict) -> str:
    for k in ("plan", "title", "status"):
        v = s.get(k)
        if isinstance(v, str) and v:
            return v[:500]
    return ""


def _pr_number(url_or_num) -> int | None:
    if isinstance(url_or_num, int):
        return url_or_num
    try:
        return int(str(url_or_num).rstrip("/").split("/")[-1])
    except Exception:
        return None
