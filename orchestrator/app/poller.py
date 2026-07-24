"""Background poll loop: track active Devin sessions, ingest their structured output, monitor
proxy-PR CI, and drive the required `devin/compliance` check. Devin does the fixing; we observe.
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
                if r.get("phase") == "done":
                    continue
                await _tick(store, devin, gh, r)
        except Exception as e:
            store.log("error", f"poller: {e}")
        await asyncio.sleep(POLL_SECS)


async def _tick(store, devin, gh, r: dict[str, Any]) -> None:
    sid = r.get("session_id")
    pr = r["pr"]
    if not sid:
        return
    s = await asyncio.to_thread(devin.get_session, sid)
    phase = devin.phase(s.get("status_enum"))
    structured = s.get("structured_output") or {}
    plan = _plan_text(s)

    fields: dict[str, Any] = {"phase": phase}
    if plan:
        fields["plan"] = plan
    if structured:
        fields["structured"] = structured
        findings = structured.get("findings") or []
        if findings:
            store.add_findings(pr, [{
                "id": f.get("id", f"F{i}"), "scanner": f.get("scanner"), "control": f.get("control"),
                "severity": f.get("severity", "medium"), "message": f.get("message", ""),
                "fixable": f.get("fixed") is not None,
                "status": "remediated" if f.get("fixed") else "open",
            } for i, f in enumerate(findings)])
        if structured.get("proxy_pr"):
            fields["proxy_pr"] = _pr_number(structured["proxy_pr"])

    # When Devin's review is complete, record the comment time (MTTR) + pass the "reviewed" check.
    if phase == "done" and not r.get("commented"):
        fields["commented"] = time.time()
        if gh and r.get("head_sha"):
            try:
                await asyncio.to_thread(
                    gh.set_required_check, r["head_sha"], "success",
                    "Sentinel review complete — see PR comment", r.get("session_url", ""))
                fields["check_state"] = "success"
            except Exception as e:
                store.log("warn", f"set check success failed: {e}", pr)
        store.log("reviewed", f"Devin finished review of PR #{pr}", pr)

    store.upsert_review(pr, **fields)

    # Monitor the proxy PR's CI (human merges it → the scanner Action goes green).
    if gh and r.get("proxy_pr"):
        try:
            p = await asyncio.to_thread(gh.get_pr, int(r["proxy_pr"]))
            ci = await asyncio.to_thread(gh.ci_conclusion, p["head"]["sha"])
            store.upsert_review(pr, structured={**(r.get("structured") or {}), "proxy_ci": ci})
        except Exception:
            pass


def _plan_text(s: dict) -> str:
    # Devin may expose a plan / latest message; keep whatever's most useful for the dashboard.
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
