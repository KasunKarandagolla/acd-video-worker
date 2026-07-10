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

CURRENT_STAGE="install_runtime_dependencies"
log_stage "Installing runtime dependencies"
bash bootstrap/install_runtime_dependencies.sh

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

CURRENT_STAGE="search_capability_preflight"
log_stage "Search capability preflight"
python3 scripts/search_capability_preflight.py
SEARCH_STATUS=$(python3 -c "
import json
try:
    with open('state/runs/search_capability_preflight.json') as f:
        d = json.load(f)
    print(d.get('current_event_fact_verification', 'blocked'))
except Exception:
    print('blocked')
")
if [ "$SEARCH_STATUS" = "blocked" ]; then
    echo ""
    echo "=== SEARCH BLOCKED ==="
    SEARCH_BLOCKER=$(python3 -c "
import json
try:
    with open('state/runs/search_capability_preflight.json') as f:
        d = json.load(f)
    print(d.get('blocker', 'No search/retrieval capability available.'))
except Exception:
    print('No search/retrieval capability available.')
")
    CURRENT_STAGE="search_blocked"
    notify "Search capability blocked: $SEARCH_BLOCKER"
    exit 1
fi
# For current-event jobs, limited (retrieval-only) also blocks
if [ "$SEARCH_STATUS" = "limited" ]; then
    echo ""
    echo "=== SEARCH LIMITED — CURRENT-EVENT JOBS BLOCKED ==="
    CURRENT_STAGE="search_limited"
    notify "Search capability limited (retrieval-only, no real search query engine). Current-event jobs blocked."
    exit 1
fi
echo "Search capability preflight: $SEARCH_STATUS — proceeding."

CURRENT_STAGE="runtime_smoke_test"
log_stage "Runtime smoke test"
python3 scripts/runtime_smoke_test.py
SMOKE_STATUS=$(python3 -c "
import json
try:
    with open('state/runs/runtime_smoke_test.json') as f:
        d = json.load(f)
    print(d.get('smoke_test_passed', False))
except Exception:
    print('false')
")
if [ "$SMOKE_STATUS" != "True" ]; then
    echo "=== SMOKE TEST FAILED ==="
    CURRENT_STAGE="smoke_test_failed"
    notify "Smoke test failed — blocking job start"
    exit 1
fi
echo "Smoke test passed — proceeding to job."

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
