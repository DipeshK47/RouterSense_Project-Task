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
  set -- --env-file config.env --headed --skip-login --max-messages 10
fi

PYTHON_BIN="python3"
if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
fi

log "Starting Q2 submission run."
log "Working directory: $ROOT_DIR"
log "Python interpreter: $PYTHON_BIN"
log "Command arguments: $*"
log "Outputs will be written to: $ROOT_DIR/outputs"

"$PYTHON_BIN" run_poc.py "$@"

log "Q2 submission run complete."
log "Transcript CSV: $ROOT_DIR/outputs/chat_transcript.csv"
log "Transcript JSON: $ROOT_DIR/outputs/chat_transcript.json"
log "Run log: $ROOT_DIR/outputs/run_log.txt"
log "Report: $ROOT_DIR/outputs/q2_automation_poc_report.md"
log "Q1 update report: $ROOT_DIR/outputs/q1_updates_from_q2.md"
