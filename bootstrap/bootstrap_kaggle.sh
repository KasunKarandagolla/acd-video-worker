#!/usr/bin/env bash
set -e

STAGE_LOG="state/runs/bootstrap_stages.log"
mkdir -p state/runs

log_stage() {
    local msg="$1"
    echo ""
    echo "========================================"
    echo "  STAGE: $msg"
    echo "========================================"
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $msg" >> "$STAGE_LOG"
}

notify() {
    local msg="$1"
    python3 scripts/discord_notify.py "$msg" 2>/dev/null || true
}

cleanup() {
    local exit_code=$?
    echo ""
    echo "=== CLEANUP ==="
    if [ "$exit_code" -eq 0 ]; then
        notify "✅ Worker completed successfully."
    else
        notify "❌ Worker failed at stage: $CURRENT_STAGE (exit code $exit_code)"
    fi
    # Attempt memory collect even on failure if run_id exists
    if [ -n "$RUN_ID" ] && [ -d "state/runs/$RUN_ID" ]; then
        echo "Attempting memory collect..."
        python3 scripts/memory_sync.py collect --run-id "$RUN_ID" 2>/dev/null || true
        python3 scripts/memory_sync.py push --run-id "$RUN_ID" 2>/dev/null || true
    fi
    echo "=== CLEANUP DONE ==="
    exit "$exit_code"
}
trap cleanup EXIT

CURRENT_STAGE="worker_started"
notify "🚀 Worker started on Kaggle"

CURRENT_STAGE="environment_check"
log_stage "Environment check"
bash bootstrap/check_environment.sh

CURRENT_STAGE="clone_repos"
log_stage "Cloning external repos"
bash bootstrap/clone_repos.sh

CURRENT_STAGE="install_skills"
log_stage "Installing skill system"
bash bootstrap/install_skills.sh

CURRENT_STAGE="llm_key_check"
log_stage "LLM API key check"
python3 scripts/llm_key_check.py

LLM_STATUS=$(python3 -c "
import json
try:
    with open('state/runs/llm_key_check.json') as f:
        d = json.load(f)
    print(d.get('llm_status', 'unknown'))
except Exception:
    print('unknown')
")
if [ "$LLM_STATUS" = "blocked" ]; then
    LLM_ERROR=$(python3 -c "
import json
try:
    with open('state/runs/llm_key_check.json') as f:
        d = json.load(f)
    print(d.get('error', 'unknown error')[:200])
except Exception:
    print('unknown error')
")
    echo ""
    echo "=== LLM BLOCKED ==="
    echo "LLM endpoint is not accessible after retries."
    CURRENT_STAGE="llm_blocked"
    notify "LLM blocked: $LLM_ERROR"
    exit 1
fi

CURRENT_STAGE="memory_hydrate"
log_stage "Memory hydrate"
python3 scripts/memory_sync.py hydrate

CURRENT_STAGE="repo_preflight"
log_stage "Repo preflight"
python3 scripts/repo_preflight.py

CURRENT_STAGE="title_theme_job"
log_stage "Running title/theme job"
JOB_FILE="${1:-jobs/argentina_hardest_victory.yaml}"
RUN_ID=$(python3 -c "import sys, datetime; print(datetime.datetime.utcnow().strftime('run_%Y%m%d_%H%M%S'))")
export RUN_ID
python3 scripts/run_title_theme_job.py "$JOB_FILE" --run-id "$RUN_ID"

CURRENT_STAGE="memory_collect"
log_stage "Memory collect"
python3 scripts/memory_sync.py collect --run-id "$RUN_ID"
python3 scripts/memory_sync.py push --run-id "$RUN_ID"

CURRENT_STAGE="worker_complete"
log_stage "Worker complete"
echo "All stages completed successfully."
