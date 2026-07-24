"""Devin API client — the ONLY place we talk to Devin. Verified endpoints:
  POST /v1/sessions            {prompt, title?, idempotent?, tags?}  -> {session_id, url}
  GET  /v1/session/{id}                                              -> {status_enum, structured_output, ...}
  GET  /v1/sessions?limit=&offset=                                   -> {sessions: [...]}
  POST /v1/session/{id}/message  {message}                          -> steer a live session
Base: https://api.devin.ai/v1  ·  Auth: Authorization: Bearer $DEVIN_API_KEY
"""
# TODO Phase 2: create_session / get_session / list_sessions / send_message (httpx)
