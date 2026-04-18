#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

timestamp() {
  date +"%Y-%m-%d %H:%M:%S"
}

log() {
  printf '\n[%s] %s\n' "$(timestamp)" "$1"
}

log "Running full submission workflow."
log "Step 1/2: Q1 evaluation"
bash "$ROOT_DIR/q1_app_evaluation/run_submission.sh"

log "Step 2/2: Q2 automation proof of concept"
bash "$ROOT_DIR/q2_automation_poc/run_submission.sh"

log "Full submission workflow complete."
