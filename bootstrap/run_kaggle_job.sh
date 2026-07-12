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

PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}" \
  python3 "$PROJECT_ROOT/scripts/acd_worker.py" "$@"
status=$?

# Persistence export is best-effort and never rewrites the production result.
python3 "$PROJECT_ROOT/scripts/kaggle_persistence.py" export || true
exit "$status"
