"""Background poll loop: for each active session GET /v1/session/{id}; for each proxy PR read CI.
When a proxy PR CI is red, send Devin a message to iterate (bounded rounds). Update state.
"""
# TODO Phase 2
