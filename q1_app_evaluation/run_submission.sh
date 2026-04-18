#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

timestamp() {
  date +"%Y-%m-%d %H:%M:%S"
}

log() {
  printf '[%s] %s\n' "$(timestamp)" "$1"
}

if [ "$#" -eq 0 ]; then
  set -- --max-web-checks 100 --web-timeout 10
fi

PYTHON_BIN="python3"
if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
fi

log "Starting Q1 submission run."
log "Working directory: $ROOT_DIR"
log "Python interpreter: $PYTHON_BIN"
log "Command arguments: $*"
log "Outputs will be written to: $ROOT_DIR/outputs"

"$PYTHON_BIN" run_q1_evaluation.py "$@"

log "Q1 submission run complete."
log "CSV: $ROOT_DIR/outputs/ai_companion_app_evaluation.csv"
log "Audit: $ROOT_DIR/outputs/evaluation_audit.md"
log "Manual review file: $ROOT_DIR/outputs/manual_review_candidates.csv"
log "Evidence log: $ROOT_DIR/outputs/evidence_log.csv"
