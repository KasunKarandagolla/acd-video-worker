#!/usr/bin/env bash
# Thin Kaggle launcher: hydrate -> one production command -> export.

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export HERMES_HOME="${HERMES_HOME:-/kaggle/working/.hermes}"
export HERMES_PROFILE="${HERMES_PROFILE:-football-emotion}"
export OPENMONTAGE_ROOT="${OPENMONTAGE_ROOT:-$PROJECT_ROOT/external/OpenMontage}"
export OPENMONTAGE_PROJECTS_DIR="${OPENMONTAGE_PROJECTS_DIR:-/kaggle/working/projects}"
export ACD_STATE_DIR="${ACD_STATE_DIR:-/kaggle/working/acd-state/runs}"

python3 "$PROJECT_ROOT/scripts/kaggle_persistence.py" hydrate
hydrate_status=$?
if [[ "$hydrate_status" -ne 0 ]]; then
  echo "Persistence hydration failed; refusing to start production." >&2
  exit "$hydrate_status"
fi

PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}" \
  python3 "$PROJECT_ROOT/scripts/acd_worker.py" "$@"
status=$?

# Any run without a committed persistence generation is not safely resumable.
# A persistence failure therefore overrides DELIVERED, BLOCKED and FAILED: the
# JSON printed above remains diagnostic evidence, but the notebook must not
# mistake an uncommitted run for a durable terminal state.
python3 "$PROJECT_ROOT/scripts/kaggle_persistence.py" export
persist_status=$?
if [[ "$persist_status" -ne 0 ]]; then
  echo "Persistence export failed; run state is not durable." >&2
  status=1
fi
exit "$status"
