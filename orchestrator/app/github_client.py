"""GitHub client (personal account, GH_PERSONAL_TOKEN). Responsibilities:
  - set the REQUIRED commit status/check `devin/compliance` (pending|blocked|passed) on a PR
  - read a PR's CI (check-runs / workflow_run conclusions) for the proxy-PR monitor loop
  - post the required human-digestible comment on the main PR
  - open the proxy PR (sentinel/compliance-<pr#> -> feature branch)
"""
# TODO Phase 2
