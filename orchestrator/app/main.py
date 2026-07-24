"""Sentinel orchestrator (FastAPI). Does NO engineering — routes events, sets required checks,
polls Devin, relays chat. Devin does the work.

Routes (skeleton):
  POST /webhook/github     - pull_request.opened/.synchronize, workflow_run  -> spawn/steer Devin
  GET  /api/state          - dashboard: instances, PRs, CI, findings, POA&M, plans
  POST /api/chat           - chat: query state OR steer a session (POST /v1/session/{id}/message)
  GET  /healthz
"""
from fastapi import FastAPI

app = FastAPI(title="Sentinel Orchestrator")


@app.get("/healthz")
def healthz():
    return {"ok": True}

# TODO Phase 2: webhook handler -> playbook -> devin.create_session -> state; poller startup;
#               dashboard /api/state; /api/chat relay.
