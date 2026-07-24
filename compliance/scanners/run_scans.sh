#!/usr/bin/env bash
# Sentinel compliance scan suite — 8 static scanners, run by Devin in-container (and by the
# required GitHub Action). Each scanner is install-or-skip so this runs anywhere. Raw outputs land
# in $OUT/raw/, then normalize.py folds them into a single control-mapped findings.json + summary.md.
#
# Usage: run_scans.sh <target_repo_dir> [out_dir]
#   TARGET  repo to scan (default: cwd)
#   OUT     results dir   (default: ./sentinel-scan)
# Exit code: 2 if any HIGH/CRITICAL finding (the merge gate), else 0.
set -uo pipefail

TARGET="${1:-$(pwd)}"
OUT="${2:-$TARGET/sentinel-scan}"
RAW="$OUT/raw"
mkdir -p "$RAW"
cd "$TARGET"

log() { printf '  [scan] %s\n' "$*" >&2; }
have() { command -v "$1" >/dev/null 2>&1; }

# ---- SAST: Semgrep (SA-11, RA-5) --------------------------------------------
if have semgrep || pip install -q semgrep 2>/dev/null; then
  log "semgrep (SAST)…"
  semgrep --config=auto --json --quiet -o "$RAW/semgrep.json" . 2>/dev/null || true
else log "semgrep unavailable — skipped"; fi

# ---- Python SAST: Bandit (SA-11) --------------------------------------------
if have bandit || pip install -q bandit 2>/dev/null; then
  log "bandit (python SAST)…"
  bandit -r . -f json -o "$RAW/bandit.json" -q 2>/dev/null || true
else log "bandit unavailable — skipped"; fi

# ---- Secrets: Gitleaks (IA-5, SC-28) ----------------------------------------
if have gitleaks; then
  log "gitleaks (secrets)…"
  gitleaks detect --source . --report-format json --report-path "$RAW/gitleaks.json" --no-banner 2>/dev/null || true
else log "gitleaks unavailable — skipped"; fi

# ---- CVE + SBOM: Trivy (RA-5, SI-2, SR-3/4) ---------------------------------
if have trivy; then
  log "trivy (deps/fs CVE)…"
  trivy fs --scanners vuln --format json --output "$RAW/trivy.json" --quiet . 2>/dev/null || true
  log "trivy (SBOM CycloneDX)…"
  trivy fs --format cyclonedx --output "$OUT/sbom.cdx.json" --quiet . 2>/dev/null || true
else log "trivy unavailable — skipped"; fi

# ---- Dockerfile hardening: Hadolint (CM-6, CM-7) ----------------------------
if have hadolint; then
  log "hadolint (dockerfiles)…"
  : > "$RAW/hadolint.json"
  find . -type f \( -name 'Dockerfile' -o -name '*.Dockerfile' -o -name 'Dockerfile.*' \) \
    -not -path '*/node_modules/*' | while read -r df; do
      hadolint -f json "$df" 2>/dev/null >> "$RAW/hadolint.json" || true
  done
else log "hadolint unavailable — skipped"; fi

# ---- Helm/K8s hardening: kube-linter (CM-6) ---------------------------------
if have kube-linter && [ -d helm ]; then
  log "kube-linter (helm)…"
  kube-linter lint helm --format json > "$RAW/kubelinter.json" 2>/dev/null || true
else log "kube-linter unavailable or no helm/ — skipped"; fi

# ---- License compliance: pip-licenses (SR-3) --------------------------------
if have pip-licenses || pip install -q pip-licenses 2>/dev/null; then
  log "pip-licenses (license compliance)…"
  pip-licenses --format=json > "$RAW/licenses.json" 2>/dev/null || true
else log "pip-licenses unavailable — skipped"; fi

# ---- Normalize into one control-mapped findings.json + summary --------------
SCANNER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCANNER_DIR/normalize.py" "$RAW" "$OUT"
rc=$?
log "results: $OUT/findings.json  ·  $OUT/summary.md  ·  $OUT/sbom.cdx.json"
exit $rc
