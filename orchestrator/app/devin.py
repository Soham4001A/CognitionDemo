"""Devin API client — the ONLY place we talk to Devin.

Verified endpoints (see PLAN.md):
  POST /v1/sessions              {prompt, title?, idempotent?, tags?}  -> {session_id, url, ...}
  GET  /v1/session/{id}                                                -> {status_enum, structured_output, ...}
  GET  /v1/sessions?limit=&offset=                                     -> {sessions: [...]}
  POST /v1/session/{id}/message  {message}                            -> steer a live session
Base https://api.devin.ai/v1 · Auth: Authorization: Bearer $DEVIN_API_KEY
"""
from __future__ import annotations

import os
from typing import Any

import httpx

BASE = "https://api.devin.ai/v1"

TERMINAL = {"finished", "expired", "stopped", "blocked_finished"}
BLOCKED = {"blocked", "suspend_requested", "suspend_requested_frontend"}


class DevinClient:
    def __init__(self, api_key: str | None = None, timeout: float = 30.0):
        self.api_key = api_key or os.environ["DEVIN_API_KEY"]
        self._c = httpx.Client(
            base_url=BASE,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            timeout=timeout,
        )

    def create_session(self, prompt: str, *, title: str | None = None,
                       tags: list[str] | None = None, idempotent: bool = False) -> dict[str, Any]:
        body: dict[str, Any] = {"prompt": prompt}
        if title:
            body["title"] = title
        if tags:
            body["tags"] = tags
        if idempotent:
            body["idempotent"] = True
        r = self._c.post("/sessions", json=body)
        r.raise_for_status()
        return r.json()

    def get_session(self, session_id: str) -> dict[str, Any]:
        r = self._c.get(f"/session/{session_id}")
        r.raise_for_status()
        return r.json()

    def list_sessions(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        r = self._c.get("/sessions", params={"limit": limit, "offset": offset})
        r.raise_for_status()
        d = r.json()
        return d.get("sessions", d) if isinstance(d, dict) else d

    def send_message(self, session_id: str, message: str) -> dict[str, Any]:
        r = self._c.post(f"/session/{session_id}/message", json={"message": message})
        r.raise_for_status()
        return r.json() if r.content else {"ok": True}

    @staticmethod
    def phase(status_enum: str | None) -> str:
        """Normalize Devin's status_enum into: running | blocked | done."""
        s = (status_enum or "").lower()
        if s in TERMINAL:
            return "done"
        if s in BLOCKED:
            return "blocked"
        return "running"

    def close(self):
        self._c.close()
