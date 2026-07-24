"""GitHub client — how the orchestrator acts on the target fork as the personal account.

Uses GH_PERSONAL_TOKEN (fine-grained PAT: Contents R/W, Issues R/W, Pull requests R/W,
Commit statuses R/W). Responsibilities:
  - set the REQUIRED commit status `devin/compliance` (pending|success|failure) on a PR's head sha
  - post the required, human-digestible comment on a PR
  - read a PR (head sha, branches) and its CI conclusion (for the proxy-PR monitor loop)
"""
from __future__ import annotations

import os
from typing import Any

import httpx

API = "https://api.github.com"
CHECK_CONTEXT = "devin/compliance"


class GitHubClient:
    def __init__(self, repo: str, token: str | None = None):
        # repo = "owner/name"
        self.owner, self.name = repo.split("/", 1)
        self.token = token or os.environ.get("GH_PERSONAL_TOKEN", "")
        self._c = httpx.Client(
            base_url=API,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    def _r(self, method: str, path: str, **kw) -> Any:
        resp = self._c.request(method, path, **kw)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def get_pr(self, number: int) -> dict[str, Any]:
        return self._r("GET", f"/repos/{self.owner}/{self.name}/pulls/{number}")

    def pr_head_sha(self, number: int) -> str:
        """Live head sha of a PR. Devin's docs auto-commit advances the feature branch, so the
        required check must be re-pinned to THIS sha or it strands on a stale commit."""
        try:
            return self.get_pr(number).get("head", {}).get("sha", "")
        except Exception:
            return ""

    def find_open_pr_by_head(self, head_branch: str) -> int | None:
        """Find an OPEN PR whose head is `head_branch` (e.g. sentinel/compliance-<pr>). Lets the
        poller detect Devin's proxy PR without waiting for it to land in structured_output."""
        try:
            prs = self._r("GET", f"/repos/{self.owner}/{self.name}/pulls",
                          params={"state": "open", "head": f"{self.owner}:{head_branch}"})
            return prs[0]["number"] if prs else None
        except Exception:
            return None

    def set_required_check(self, sha: str, state: str, description: str, target_url: str = "") -> None:
        """state ∈ pending|success|failure|error. Set the `devin/compliance` commit status —
        make this context a required check in branch protection to gate merges."""
        self._r("POST", f"/repos/{self.owner}/{self.name}/statuses/{sha}", json={
            "state": state, "context": CHECK_CONTEXT,
            "description": description[:140], "target_url": target_url,
        })

    def comment(self, pr_number: int, body: str) -> dict[str, Any]:
        return self._r("POST", f"/repos/{self.owner}/{self.name}/issues/{pr_number}/comments",
                       json={"body": body})

    def ci_conclusion(self, sha: str) -> str:
        """Aggregate CI for a sha across check-runs + legacy statuses:
        returns pending | success | failure (worst-wins)."""
        runs = self._r("GET", f"/repos/{self.owner}/{self.name}/commits/{sha}/check-runs")
        concls = [c.get("conclusion") for c in runs.get("check_runs", [])
                  if c.get("name") != CHECK_CONTEXT]
        statuses = self._r("GET", f"/repos/{self.owner}/{self.name}/commits/{sha}/status")
        # any not-yet-complete → pending
        if any(c is None for c in concls) or statuses.get("state") == "pending":
            return "pending"
        bad = {"failure", "timed_out", "cancelled", "action_required", "error"}
        if any(c in bad for c in concls) or statuses.get("state") in {"failure", "error"}:
            return "failure"
        return "success"

    def close(self):
        self._c.close()
