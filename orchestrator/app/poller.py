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

    # Proxy-PR detection independent of structured_output: Devin only writes structured output at
    # the very end (session may sit in working/blocked with the proxy PR already open). Detect it by
    # its branch so the gate can advance to "awaiting approval" the moment the PR exists.
    proxy = fields.get("proxy_pr") or r.get("proxy_pr")
    if not proxy and gh:
        found = await asyncio.to_thread(gh.find_open_pr_by_head, f"sentinel/compliance-{pr}")
        if found:
            proxy = found
            fields["proxy_pr"] = found
            store.log("proxy", f"detected proxy PR #{found} for PR #{pr}", pr)

    # Keep the required check pinned to the LIVE head sha. Devin's docs auto-commit advances the
    # feature branch, which strands a status set on the prior sha — re-pin so the gate stays on the
    # actually-mergeable commit.
    head_sha = r.get("head_sha")
    if gh:
        live_sha = await asyncio.to_thread(gh.pr_head_sha, pr)
        if live_sha and live_sha != head_sha:
            store.log("head", f"PR #{pr} head advanced {(head_sha or '')[:8]}→{live_sha[:8]} — re-pinning check", pr)
            head_sha = live_sha
            fields["head_sha"] = live_sha

    # Review is materially complete once Devin is done OR its proxy PR is open (scan + remediation
    # landed). Bare `blocked` is ambiguous — Devin may be stuck mid-work asking a question — so it is
    # NOT a completion signal on its own, or we'd resolve the gate to success prematurely.
    review_complete = phase == "done" or bool(proxy)
    if review_complete and not r.get("commented"):
        fields["commented"] = time.time()
        store.log("reviewed", f"Devin review of PR #{pr} complete (proxy PR {proxy or 'none'})", pr)

    if review_complete or r.get("commented"):
        state, desc, resolved = await _gate(gh, proxy)
        fields["check_state"] = state
        if resolved:
            fields["phase"] = "resolved"
        # Only write the status when it actually changed — the poll loop runs every 15s and would
        # otherwise spam the PR's status history with identical rows (noise in the audit trail).
        sig = f"{head_sha}:{state}:{desc}"
        if gh and head_sha and sig != r.get("check_sig"):
            try:
                await asyncio.to_thread(gh.set_required_check, head_sha, state, desc,
                                        r.get("session_url", ""))
                fields["check_sig"] = sig
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
