#!/usr/bin/env bash
# Reproducible Kaggle bootstrap for the thin ACD runtime.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="$PROJECT_ROOT/bootstrap"
export HERMES_HOME="${HERMES_HOME:-/kaggle/working/.hermes}"
export HERMES_PROFILE="${HERMES_PROFILE:-football-emotion}"
export OPENMONTAGE_ROOT="${OPENMONTAGE_ROOT:-$PROJECT_ROOT/external/OpenMontage}"
export OPENMONTAGE_PROJECTS_DIR="${OPENMONTAGE_PROJECTS_DIR:-/kaggle/working/projects}"
export ACD_STATE_DIR="${ACD_STATE_DIR:-/kaggle/working/acd-state/runs}"
export ACD_PERSIST_EXPORT="${ACD_PERSIST_EXPORT:-/kaggle/working/acd-persist-export}"
export OPENMONTAGE_PYTHON_VERSION="${OPENMONTAGE_PYTHON_VERSION:-3.11}"
export PATH="$HOME/.local/bin:$PATH"

log() { printf '\033[1;33m→\033[0m %s\n' "$*"; }
ok() { printf '\033[0;32m✓\033[0m %s\n' "$*"; }

mkdir -p "$HERMES_HOME" "$OPENMONTAGE_PROJECTS_DIR" "$ACD_STATE_DIR"
python3 "$PROJECT_ROOT/scripts/kaggle_persistence.py" hydrate
python3 -m pip install -r "$PROJECT_ROOT/requirements.txt"

log "Installing pinned Hermes-Agent"
bash "$SCRIPT_DIR/install_hermes.sh"

if hermes profile list 2>/dev/null | grep -q "football-emotion"; then
    ok "Hermes profile exists"
else
    hermes profile create football-emotion --clone-all
    ok "Hermes profile created"
fi

set +e
python3 "$SCRIPT_DIR/configure_hermes_profile.py"
PROFILE_STATUS=$?
set -e
if [[ "$PROFILE_STATUS" -ne 0 && "$PROFILE_STATUS" -ne 2 ]]; then
    exit "$PROFILE_STATUS"
fi

log "Installing pinned OpenMontage with native local render runtimes"
if [[ ! -d "$OPENMONTAGE_ROOT/.git" ]]; then
    git clone https://github.com/calesthio/OpenMontage.git "$OPENMONTAGE_ROOT"
fi
git -C "$OPENMONTAGE_ROOT" fetch origin
git -C "$OPENMONTAGE_ROOT" checkout f633b5f428b9be9a2afecba851dfddd101619756
python3 "$PROJECT_ROOT/bootstrap/apply_openmontage_compatibility.py" \
    --worker-root "$PROJECT_ROOT" \
    --openmontage-root "$OPENMONTAGE_ROOT"

# Kaggle's system Python 3.10 lacks ensurepip. Create a complete isolated
# environment without modifying the pinned OpenMontage repository.
if [[ ! -x "$OPENMONTAGE_ROOT/.venv/bin/python" ]] || \
   ! "$OPENMONTAGE_ROOT/.venv/bin/python" -m pip --version >/dev/null 2>&1; then
    uv venv --clear --seed --python "$OPENMONTAGE_PYTHON_VERSION" "$OPENMONTAGE_ROOT/.venv"
fi

"$OPENMONTAGE_ROOT/.venv/bin/python" -m pip install -r "$OPENMONTAGE_ROOT/requirements.txt"
if [[ ! -x "$OPENMONTAGE_ROOT/remotion-composer/node_modules/.bin/remotion" ]]; then
    npm ci --prefix "$OPENMONTAGE_ROOT/remotion-composer" --no-audit --no-fund
fi
log "Pre-installing the Remotion browser during bootstrap"
(cd "$OPENMONTAGE_ROOT/remotion-composer" && npx --no-install remotion browser ensure)
"$OPENMONTAGE_ROOT/.venv/bin/python" -m pip install -r "$PROJECT_ROOT/requirements.txt"

log "Installing complete Football Emotion Skill System"
bash "$SCRIPT_DIR/install_skills.sh"

log "Running thin-runtime doctor"
PYTHONPATH="$PROJECT_ROOT/src" python3 "$PROJECT_ROOT/bootstrap/validate_setup.py"

python3 "$PROJECT_ROOT/scripts/kaggle_persistence.py" export
ok "Kaggle setup complete"
echo "Run: bash $PROJECT_ROOT/bootstrap/run_kaggle_job.sh \"<video request>\" [--input ...]"
