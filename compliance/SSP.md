# System Security Plan (SSP) — superset-cognition-demo

> **Seed SSP** for the Apache Superset fork under continuous-compliance automation by **Sentinel**.
> Sentinel (via Devin) maintains this document: when a PR changes a control's implementation, Devin
> updates the relevant control below; every scanner finding becomes a POA&M item (see `POAM.md`).
> Scope: a demonstration ATO-style baseline — real controls, lightly populated. Not an accredited SSP.

## 1. System description

Apache Superset — a data-exploration and visualization web application. Stack: Python (Flask) backend,
TypeScript/React frontend, Postgres/Redis dependencies, packaged via Docker + a Helm chart. This fork
(`superset-cognition-demo`) is the target of an autonomous compliance + documentation gate on every PR.

- **Authorization boundary:** the container images (backend, frontend), the Helm chart, and the
  build/supply-chain (Python + npm dependencies, Dockerfiles).
- **Data:** demonstration only; no CUI/PII in this fork.

## 2. Control implementation summary

Each control lists its **implementation** and the **automated evidence** Sentinel produces per PR.

| Control | Title | Implementation | Automated evidence (Sentinel) |
|---|---|---|---|
| **RA-5** | Vulnerability Monitoring & Scanning | Every PR is scanned for CVEs + SAST findings before merge | Trivy (deps/image), Semgrep, Bandit — findings → POA&M |
| **SI-2** | Flaw Remediation | Fixable findings are remediated by Devin via a reviewed proxy PR | proxy PR + POA&M status transition Open→Remediated |
| **SA-11** | Developer Testing & Evaluation | SAST runs on every change; results block merge until triaged | Semgrep + Bandit gate on the required check |
| **SR-3 / SR-4** | Supply Chain Controls / Provenance | SBOM generated per build; dependency licenses enforced | Trivy CycloneDX SBOM + `pip-licenses` allowlist |
| **IA-5 / SC-28** | Authenticator Mgmt / Protection at Rest | No secrets committed to the repo | Gitleaks secret scan (required) |
| **CM-6 / CM-7** | Configuration Settings / Least Functionality | Container + K8s configs are linted against hardening rules | Hadolint (Dockerfiles) + kube-linter (Helm) |
| **CM-2 / CM-3** | Baseline Config / Change Control | Docs are kept in lockstep with code; PRs can't drift docs | docs-currency build + Devin doc-sync commit |
| **SA-5** | System Documentation | Documentation builds and matches the current diff | Superset docs build validation |
| **CA-7** | Continuous Monitoring | Compliance posture is measured continuously, not point-in-time | the Sentinel dashboard (findings burn-down, MTTR) |

## 3. Automated assessment procedure

On every `pull_request.opened`, Sentinel dispatches Devin to: (a) validate documentation currency
against the diff and fix drift on the feature branch; (b) run the scanner suite in an isolated
container; (c) remediate fixable findings via a human-approved proxy PR; (d) file each finding as a
POA&M item mapped to the control above; (e) post a required, human-digestible review comment; and
(f) hold merge (required check `devin/compliance`) until satisfied. See `../PLAN.md` for the loop.

## 4. Change log

| Date | PR | Change | By |
|---|---|---|---|
| _seed_ | — | Initial baseline SSP | Sentinel |
