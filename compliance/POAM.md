# Plan of Action & Milestones (POA&M) — superset-cognition-demo

> Maintained by **Sentinel** (via Devin). Every scanner finding on a PR becomes a row here, mapped to
> the 800-53 control it evidences (see `SSP.md`). Status transitions: **Open** → **In Remediation**
> (proxy PR opened) → **Remediated** (proxy PR merged) → **Accepted-Risk** (human waiver). The Sentinel
> dashboard renders the live burn-down + MTTR from these rows.

| ID | Finding | Scanner | Control | Severity | Status | PR | Proxy PR | Opened | Remediation |
|----|---------|---------|---------|----------|--------|----|----------|--------|-------------|
| POAM-0001 | _example: hardcoded fallback secret in config_ | Gitleaks | IA-5 | High | Open | — | — | _seed_ | replace with env-injected secret |

<!-- SENTINEL:POAM-ROWS -->
<!-- Devin appends new POA&M rows directly above this marker, one per finding. -->

## Summary (auto-updated)

| Metric | Value |
|---|---|
| Open | 0 |
| In Remediation | 0 |
| Remediated | 0 |
| Accepted-Risk | 0 |
| Mean time to remediation (MTTR) | — |
