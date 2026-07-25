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
import re
import time
from typing import Any

POLL_SECS = 15


async def poll_loop(store, devin, gh) -> None:
    while True:
        try:
            for r in store.list_reviews():
                if r.get("phase") == "closed":
                    continue  # main PR merged/closed — nothing left to gate
                await _tick(store, devin, gh, r)
            for t in store.list_tasks():
                if t.get("phase") in ("resolved", "closed"):
                    continue  # issue remediated + closed — terminal
                await _task_tick(store, devin, gh, t)
        except Exception as e:
            store.log("error", f"poller: {e}")
        await asyncio.sleep(POLL_SECS)


async def _task_tick(store, devin, gh, t: dict[str, Any]) -> None:
    """Track one issue-remediation task: Devin session -> remediation PR -> issue closed."""
    issue = t["issue"]
    sid = t.get("session_id")
    fields: dict[str, Any] = {}
    phase = t.get("phase")
    fixed = False

    if sid:
        s = await asyncio.to_thread(devin.get_session, sid)
        phase = devin.phase(s.get("status_enum"))
        fields["phase"] = phase
        so = s.get("structured_output") or {}
        if so:
            fixed = bool(so.get("fixed"))
            if so.get("control") and not t.get("control"):
                fields["control"] = so["control"]
            if so.get("severity") and not t.get("severity"):
                fields["severity"] = so["severity"]
            if so.get("pr") and not t.get("pr_number"):
                fields["pr_number"] = _pr_number(so["pr"])
            if so.get("summary"):
                fields["summary"] = str(so["summary"])[:400]
            if so.get("scanner_evidence"):
                fields["evidence"] = str(so["scanner_evidence"])[:400]

    # Control chip: Devin often leaves structured_output blank, but the issue title carries the
    # mapping (e.g. "[CM-6/CM-7] Harden…") — backfill it so every card shows its 800-53 control.
    if not (fields.get("control") or t.get("control")):
        cm = re.match(r"\s*\[([^\]]+)\]", t.get("title") or "")
        if cm:
            fields["control"] = cm.group(1)

    # Detect the remediation PR by its branch, independent of structured_output.
    pr_number = fields.get("pr_number") or t.get("pr_number")
    if not pr_number and gh:
        found = await asyncio.to_thread(gh.find_open_pr_by_head, f"sentinel/issue-{issue}")
        if found:
            pr_number = found
            fields["pr_number"] = found
            store.log("remediate", f"issue #{issue}: remediation PR #{found} opened", issue)

    if pr_number and gh and not (fields.get("summary") or t.get("summary")):
        # Devin doesn't always fill structured_output, but it ALWAYS writes a PR body — derive the
        # human-readable "what Devin did" from there so the dashboard shows real work, not a blank.
        try:
            p = await asyncio.to_thread(gh.get_pr, int(pr_number))
            summ = _extract_summary(p.get("body") or "") or p.get("title", "")
            if summ:
                fields["summary"] = summ[:400]
        except Exception:
            pass

    if pr_number and gh:
        # Stamp devin/compliance on the remediation PR (Devin's own vetted fix) so it can merge under
        # branch protection: pending while Devin works, success once the fix is in and reviewable.
        # `blocked` counts as ready here — the remediation PR already exists (pr_number is set), so the
        # fix has been pushed; Devin lingering in blocked/awaiting is not "still working".
        ready = phase in ("done", "blocked") or fixed
        state = "success" if ready else "pending"
        desc = (f"Sentinel remediation for issue #{issue} — ready for review" if ready
                else f"Sentinel remediating issue #{issue}…")
        try:
            head = await asyncio.to_thread(gh.pr_head_sha, pr_number)
            sig = f"{head}:{state}:{desc}"
            if head and sig != t.get("check_sig"):
                await asyncio.to_thread(gh.set_required_check, head, state, desc, t.get("session_url", ""))
                fields["check_sig"] = sig
                fields["check_state"] = state
        except Exception as e:
            store.log("warn", f"task #{issue} set check failed: {e}", issue)
        # Issue closes when a human merges the PR (body says `Closes #issue`) — that's remediation done.
        try:
            iss = await asyncio.to_thread(gh.get_issue, issue)
            if iss.get("state") == "closed":
                fields["phase"] = "resolved"
                fields["resolved"] = time.time()
                store.log("resolved", f"issue #{issue} remediated + closed (PR #{pr_number})", issue)
        except Exception:
            pass

    store.update_task(issue, **fields)


async def _tick(store, devin, gh, r: dict[str, Any]) -> None:
    pr = r["pr"]
    sid = r.get("session_id")
    fields: dict[str, Any] = {}
    # Once the gate is decided we stop polling Devin but keep re-pinning the check to the live head
    # (until the main PR closes), so don't early-return on a resolved review.
    decided_already = r.get("phase") == "resolved"
    phase = r.get("phase")

    if sid and not decided_already:
        s = await asyncio.to_thread(devin.get_session, sid)
        phase = devin.phase(s.get("status_enum"))
        fields["phase"] = phase
        plan = _plan_text(s)
        if plan:
            fields["plan"] = plan
        structured = s.get("structured_output") or {}
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

    # Proxy-PR detection independent of structured_output: Devin only writes structured output at the
    # very end. Detect it by its branch so the gate advances the moment the PR exists.
    proxy = fields.get("proxy_pr") or r.get("proxy_pr")
    if not proxy and gh:
        found = await asyncio.to_thread(gh.find_open_pr_by_head, f"sentinel/compliance-{pr}")
        if found:
            proxy = found
            fields["proxy_pr"] = found
            store.log("proxy", f"detected proxy PR #{found} for PR #{pr}", pr)

    # One call for the main PR: its live head (re-pin target) AND whether it has closed (terminal).
    head_sha = r.get("head_sha")
    main_closed = False
    if gh:
        try:
            mp = await asyncio.to_thread(gh.get_pr, pr)
            live_sha = mp.get("head", {}).get("sha", "")
            main_closed = mp.get("state") == "closed"
            if live_sha and live_sha != head_sha:
                store.log("head", f"PR #{pr} head {(head_sha or '')[:8]}→{live_sha[:8]} — re-pinning check", pr)
                head_sha = live_sha
                fields["head_sha"] = live_sha
        except Exception:
            pass

    review_complete = phase == "done" or bool(proxy) or decided_already
    if review_complete and not r.get("commented"):
        fields["commented"] = time.time()
        store.log("reviewed", f"Devin review of PR #{pr} complete (proxy PR {proxy or 'none'})", pr)

    if review_complete:
        state, desc, decided = await _gate(gh, proxy)
        fields["check_state"] = state
        # 'resolved' = gate decided (for display). But keep re-pinning to the newest head until the
        # MAIN PR closes: a squash-merge of the proxy makes a fresh head commit that must ALSO carry
        # devin/compliance, or branch protection would block the main PR on an unstamped commit.
        if decided:
            fields["phase"] = "resolved"
        if main_closed:
            fields["phase"] = "closed"
        # Idempotent write — only touch GitHub when (head, state, desc) changed, so the 15s loop
        # doesn't spam the PR's status history (audit-trail noise).
        sig = f"{head_sha}:{state}:{desc}"
        if gh and head_sha and sig != r.get("check_sig"):
            try:
                await asyncio.to_thread(gh.set_required_check, head_sha, state, desc,
                                        r.get("session_url", ""))
                fields["check_sig"] = sig
            except Exception as e:
                store.log("warn", f"set check {state} failed: {e}", pr)

    store.update_review(pr, **fields)


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


def _extract_summary(body: str) -> str:
    """Pull a human-readable summary out of a Devin PR body — the `### SUMMARY` section if present,
    else the first non-marker paragraph. Strips the `Closes #N` line and markdown noise."""
    import re
    if not body:
        return ""
    m = re.search(r"#+\s*summary\s*\n(.+?)(?:\n#+\s|\Z)", body, re.I | re.S)
    chunk = m.group(1) if m else body
    for line in chunk.splitlines():
        s = line.strip().lstrip("#").strip()
        if not s or s.lower().startswith(("closes #", "fixes #", "resolves #")):
            continue
        return re.sub(r"[`*_]", "", s)
    return ""


def _pr_number(url_or_num) -> int | None:
    if isinstance(url_or_num, int):
        return url_or_num
    try:
        return int(str(url_or_num).rstrip("/").split("/")[-1])
    except Exception:
        return None
