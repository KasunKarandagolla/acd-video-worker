#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

STAGE_LOG="state/runs/bootstrap_stages.log"
mkdir -p state/runs

FINAL_EXIT_CODE=0

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
    python3 -m scripts.discord_notify "$msg" 2>/dev/null || true
}

cleanup() {
    local original_exit=$?
    trap - EXIT
    set +e

    echo ""
    echo "=== CLEANUP ==="
    if [ "$original_exit" -eq 0 ]; then
        notify "Worker completed successfully."
        echo "Pipeline completed successfully."
    else
        notify "Worker failed at stage: $CURRENT_STAGE (exit code $original_exit)"
    fi
    echo "=== CLEANUP DONE ==="

    exit "$original_exit"
}
trap cleanup EXIT

CURRENT_STAGE="worker_started"
notify "Worker started on Kaggle"

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
python3 -m scripts.llm_key_check

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
    FINAL_EXIT_CODE=1
    exit 1
fi

CURRENT_STAGE="memory_hydrate"
log_stage "Memory hydrate"
python3 -m scripts.memory_sync hydrate

CURRENT_STAGE="repo_preflight"
log_stage "Repo preflight"
python3 -m scripts.repo_preflight

CURRENT_STAGE="search_capability_preflight"
log_stage "Search capability preflight"
python3 -m scripts.search_capability_preflight
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
    FINAL_EXIT_CODE=1
    exit 1
fi
# For current-event jobs, limited (retrieval-only) also blocks
if [ "$SEARCH_STATUS" = "limited" ]; then
    echo ""
    echo "=== SEARCH LIMITED — CURRENT-EVENT JOBS BLOCKED ==="
    CURRENT_STAGE="search_limited"
    notify "Search capability limited (retrieval-only, no real search query engine). Current-event jobs blocked."
    FINAL_EXIT_CODE=1
    exit 1
fi
echo "Search capability preflight: $SEARCH_STATUS — proceeding."

CURRENT_STAGE="runtime_smoke_test"
log_stage "Runtime smoke test"
set +e
python3 -m scripts.runtime_smoke_test
SMOKE_EXIT=$?
set -e

if [[ "$SMOKE_EXIT" -ne 0 ]]; then
    CURRENT_STAGE="smoke_test_failed"
    notify "Runtime smoke test failed with exit code $SMOKE_EXIT"
    echo "=== SMOKE TEST FAILED (exit code $SMOKE_EXIT) ==="
    exit "$SMOKE_EXIT"
fi
echo "Smoke test passed."

if [[ "${HERMES_VALIDATE_ONLY:-0}" == "1" ]]; then
    echo "Mode: HERMES_VALIDATE_ONLY — validation complete. No production job."
    FINAL_EXIT_CODE=0
    exit 0
fi

if [[ "${HERMES_ARTIFACT_CANARY:-0}" == "1" ]]; then
    echo "Mode: HERMES_ARTIFACT_CANARY — will stop after Hermes artifact validation."
fi

CURRENT_STAGE="title_theme_job"
log_stage "Running title/theme job"
JOB_FILE="${1:-jobs/argentina_hardest_victory.yaml}"
RUN_ID=$(python3 -c "import sys, datetime; print(datetime.datetime.utcnow().strftime('run_%Y%m%d_%H%M%S'))")
export RUN_ID

set +e
python3 -m scripts.run_title_theme_job "$JOB_FILE" --run-id "$RUN_ID"
JOB_EXIT=$?
set -e

if [ "$JOB_EXIT" -ne 0 ]; then
    echo "=== TITLE/THEME JOB FAILED (exit code $JOB_EXIT) ==="
    CURRENT_STAGE="title_theme_job_failed"
    notify "Title/theme job failed — exit code $JOB_EXIT"
    FINAL_EXIT_CODE=$JOB_EXIT
    exit $JOB_EXIT
fi

CURRENT_STAGE="memory_collect"
log_stage "Memory collect"
python3 -m scripts.memory_sync collect --run-id "$RUN_ID"
python3 -m scripts.memory_sync push --run-id "$RUN_ID"

CURRENT_STAGE="worker_complete"
log_stage "Worker complete"
