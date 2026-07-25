"""SQLite state — the single source of truth the dashboard renders and chat reasons over.

Entities: reviews (one per PR Sentinel attaches to), findings, tickets (built-in board),
chat, events (timeline). JSON columns keep it flexible.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any

DB_PATH = os.environ.get("SENTINEL_DB", "/data/sentinel.sqlite")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
  pr INTEGER PRIMARY KEY, repo TEXT, title TEXT, head_branch TEXT, base_branch TEXT,
  head_sha TEXT, session_id TEXT, session_url TEXT, phase TEXT, check_state TEXT,
  proxy_pr INTEGER, comment_url TEXT, plan TEXT, structured TEXT, check_sig TEXT,
  created REAL, updated REAL, commented REAL
);
CREATE TABLE IF NOT EXISTS findings (
  id TEXT PRIMARY KEY, pr INTEGER, scanner TEXT, control TEXT, severity TEXT,
  message TEXT, fixable INTEGER, status TEXT, created REAL
);
CREATE TABLE IF NOT EXISTS tickets (
  id TEXT PRIMARY KEY, pr INTEGER, title TEXT, control TEXT, severity TEXT,
  status TEXT, link TEXT, created REAL
);
CREATE TABLE IF NOT EXISTS tasks (
  issue INTEGER PRIMARY KEY, title TEXT, control TEXT, severity TEXT, session_id TEXT,
  session_url TEXT, phase TEXT, pr_number INTEGER, check_state TEXT, check_sig TEXT,
  summary TEXT, evidence TEXT, created REAL, updated REAL, resolved REAL
);
CREATE TABLE IF NOT EXISTS chat (
  id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, session_id TEXT, ts REAL
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, pr INTEGER, kind TEXT, detail TEXT, ts REAL
);
"""


def _row(c: sqlite3.Cursor, r: sqlite3.Row) -> dict[str, Any]:
    d = {k: r[k] for k in r.keys()}
    if "structured" in d and d["structured"]:
        try:
            d["structured"] = json.loads(d["structured"])
        except Exception:
            pass
    return d


class Store:
    def __init__(self, path: str = DB_PATH):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(_SCHEMA)
        self._migrate()
        self.db.commit()

    def _migrate(self) -> None:
        """Additive column migrations for DBs created before a column existed (CREATE TABLE IF NOT
        EXISTS won't add them). Each ALTER is idempotent — ignore 'duplicate column' errors."""
        have = {r[1] for r in self.db.execute("PRAGMA table_info(reviews)")}
        for col, decl in (("check_sig", "TEXT"),):
            if col not in have:
                self.db.execute(f"ALTER TABLE reviews ADD COLUMN {col} {decl}")
        have_t = {r[1] for r in self.db.execute("PRAGMA table_info(tasks)")}
        for col, decl in (("summary", "TEXT"), ("evidence", "TEXT")):
            if col not in have_t:
                self.db.execute(f"ALTER TABLE tasks ADD COLUMN {col} {decl}")

    # ---- reviews ----
    def upsert_review(self, pr: int, **fields) -> None:
        fields.setdefault("updated", time.time())
        cur = self.db.execute("SELECT pr FROM reviews WHERE pr=?", (pr,))
        if cur.fetchone() is None:
            fields.setdefault("created", time.time())
            if "structured" in fields and not isinstance(fields["structured"], str):
                fields["structured"] = json.dumps(fields["structured"])
            cols = ",".join(["pr", *fields])
            qs = ",".join(["?"] * (1 + len(fields)))
            self.db.execute(f"INSERT INTO reviews ({cols}) VALUES ({qs})", (pr, *fields.values()))
        else:
            if "structured" in fields and not isinstance(fields["structured"], str):
                fields["structured"] = json.dumps(fields["structured"])
            sets = ",".join(f"{k}=?" for k in fields)
            self.db.execute(f"UPDATE reviews SET {sets} WHERE pr=?", (*fields.values(), pr))
        self.db.commit()

    def update_review(self, pr: int, **fields) -> None:
        """Update-only (never insert). The poller uses this so a row deleted by reset() while a
        session is mid-tick is not resurrected."""
        if self.db.execute("SELECT pr FROM reviews WHERE pr=?", (pr,)).fetchone() is None:
            return
        fields.setdefault("updated", time.time())
        if "structured" in fields and not isinstance(fields["structured"], str):
            fields["structured"] = json.dumps(fields["structured"])
        sets = ",".join(f"{k}=?" for k in fields)
        self.db.execute(f"UPDATE reviews SET {sets} WHERE pr=?", (*fields.values(), pr))
        self.db.commit()

    def get_review(self, pr: int) -> dict[str, Any] | None:
        r = self.db.execute("SELECT * FROM reviews WHERE pr=?", (pr,)).fetchone()
        return _row(self.db.cursor(), r) if r else None

    def list_reviews(self) -> list[dict[str, Any]]:
        rows = self.db.execute("SELECT * FROM reviews ORDER BY updated DESC").fetchall()
        return [_row(self.db.cursor(), r) for r in rows]

    # ---- findings / tickets ----
    def add_findings(self, pr: int, items: list[dict]) -> None:
        for f in items:
            self.db.execute(
                "INSERT OR REPLACE INTO findings (id,pr,scanner,control,severity,message,fixable,status,created)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (f"{pr}-{f['id']}", pr, f.get("scanner"), f.get("control"), f.get("severity"),
                 f.get("message"), int(bool(f.get("fixable"))), f.get("status", "open"), time.time()))
        self.db.commit()

    def list_findings(self, pr: int | None = None) -> list[dict[str, Any]]:
        q = "SELECT * FROM findings" + ("" if pr is None else " WHERE pr=?")
        rows = self.db.execute(q + " ORDER BY created DESC", () if pr is None else (pr,)).fetchall()
        return [dict(r) for r in rows]

    def add_ticket(self, tid: str, pr: int, title: str, control: str, severity: str,
                   status: str = "open", link: str = "") -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO tickets (id,pr,title,control,severity,status,link,created)"
            " VALUES (?,?,?,?,?,?,?,?)", (tid, pr, title, control, severity, status, link, time.time()))
        self.db.commit()

    def list_tickets(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.execute("SELECT * FROM tickets ORDER BY created DESC").fetchall()]

    def reset(self) -> None:
        """Wipe operational state for a clean demo run (schema preserved)."""
        for tbl in ("reviews", "tasks", "findings", "tickets", "events", "chat"):
            self.db.execute(f"DELETE FROM {tbl}")
        self.db.commit()

    # ---- issue-remediation tasks (issue -> Devin session -> PR that Closes #issue) ----
    def upsert_task(self, issue: int, **fields) -> None:
        fields.setdefault("updated", time.time())
        cur = self.db.execute("SELECT issue FROM tasks WHERE issue=?", (issue,))
        if cur.fetchone() is None:
            fields.setdefault("created", time.time())
            cols = ",".join(["issue", *fields])
            qs = ",".join(["?"] * (1 + len(fields)))
            self.db.execute(f"INSERT INTO tasks ({cols}) VALUES ({qs})", (issue, *fields.values()))
        else:
            sets = ",".join(f"{k}=?" for k in fields)
            self.db.execute(f"UPDATE tasks SET {sets} WHERE issue=?", (*fields.values(), issue))
        self.db.commit()

    def update_task(self, issue: int, **fields) -> None:
        """Update-only (never insert) — poller counterpart to update_review; survives reset() races."""
        if self.db.execute("SELECT issue FROM tasks WHERE issue=?", (issue,)).fetchone() is None:
            return
        fields.setdefault("updated", time.time())
        sets = ",".join(f"{k}=?" for k in fields)
        self.db.execute(f"UPDATE tasks SET {sets} WHERE issue=?", (*fields.values(), issue))
        self.db.commit()

    def get_task(self, issue: int) -> dict[str, Any] | None:
        r = self.db.execute("SELECT * FROM tasks WHERE issue=?", (issue,)).fetchone()
        return dict(r) if r else None

    def list_tasks(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.execute("SELECT * FROM tasks ORDER BY updated DESC").fetchall()]

    # ---- chat / events ----
    def add_chat(self, role: str, content: str, session_id: str | None = None) -> None:
        self.db.execute("INSERT INTO chat (role,content,session_id,ts) VALUES (?,?,?,?)",
                        (role, content, session_id, time.time()))
        self.db.commit()

    def list_chat(self, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.db.execute("SELECT * FROM chat ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in reversed(rows)]

    def log(self, kind: str, detail: str, pr: int | None = None) -> None:
        self.db.execute("INSERT INTO events (pr,kind,detail,ts) VALUES (?,?,?,?)",
                        (pr, kind, detail, time.time()))
        self.db.commit()

    def list_events(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ---- dashboard metrics ----
    def metrics(self) -> dict[str, Any]:
        reviews = self.list_reviews()
        tasks = self.list_tasks()
        findings = self.list_findings()
        remediated = [f for f in findings if f["status"] in ("remediated", "fixed")]
        mttrs = []
        for r in reviews:
            if r.get("commented") and r.get("created"):
                mttrs.append(r["commented"] - r["created"])
        # issue-remediation MTTR: dispatch -> issue resolved (PR merged/closed)
        for t in tasks:
            if t.get("resolved") and t.get("created"):
                mttrs.append(t["resolved"] - t["created"])
        return {
            "reviews": len(reviews),
            "active": sum(1 for r in reviews if r.get("phase") == "running")
            + sum(1 for t in tasks if t.get("phase") not in ("resolved", "closed", None)),
            "findings_open": sum(1 for f in findings if f["status"] == "open"),
            "findings_remediated": len(remediated),
            "issues_total": len(tasks),
            "issues_open": sum(1 for t in tasks if t.get("phase") not in ("resolved", "closed")),
            "issues_remediated": sum(1 for t in tasks if t.get("phase") in ("resolved", "closed")),
            "by_control": _count(findings, "control"),
            "by_severity": _count(findings, "severity"),
            "mttr_seconds": round(sum(mttrs) / len(mttrs), 1) if mttrs else None,
        }


def _count(items: list[dict], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for i in items:
        out[i.get(key, "?")] = out.get(i.get(key, "?"), 0) + 1
    return out
