#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${TEST_REPORT_DIR:-$ROOT_DIR/test-report}"
LOG_PATH="$REPORT_DIR/output.log"

rm -rf "$REPORT_DIR"
mkdir -p "$REPORT_DIR"

run_logged() {
  "$@" 2>&1 | tee -a "$LOG_PATH"
}

echo "release_test_started_at=$(date -Iseconds)" > "$REPORT_DIR/summary.txt"

if [[ ! -x "$ROOT_DIR/scripts/project-test.sh" ]]; then
  echo "scripts/project-test.sh is required for this repository." | tee -a "$LOG_PATH"
  exit 1
fi

run_logged "$ROOT_DIR/scripts/project-test.sh"

echo "release_test_finished_at=$(date -Iseconds)" >> "$REPORT_DIR/summary.txt"
