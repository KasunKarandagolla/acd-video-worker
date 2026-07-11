#!/usr/bin/env bash
# Kaggle bootstrap — run inside Kaggle notebook
# Sets up Hermes + OpenMontage with persistence to /kaggle/working/

set -euo pipefail

PROJECT_ROOT="/home/kasun/Music/Director/acd-video-worker"
SCRIPT_DIR="$PROJECT_ROOT/bootstrap"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${YELLOW}→${NC} $*"; }
ok() { echo -e "${GREEN}✓${NC} $*"; }
err() { echo -e "${RED}✗${NC} $*" >&2; }

# 0. Kaggle-specific environment
export HERMES_HOME="/kaggle/working/.hermes"
export OPENMONTAGE_PROJECTS_DIR="/kaggle/working/projects"

log "Setting up Kaggle persistence..."
mkdir -p "$HERMES_HOME" "$OPENMONTAGE_PROJECTS_DIR"

# Safe symlink: only if ~/.hermes doesn't exist or is a symlink
if [[ -L "$HOME/.hermes" ]]; then
    CURRENT_TARGET=$(readlink "$HOME/.hermes")
    if [[ "$CURRENT_TARGET" == "$HERMES_HOME" ]]; then
        ok "~/.hermes already points to $HERMES_HOME"
    else
        log "Updating ~/.hermes symlink from $CURRENT_TARGET to $HERMES_HOME"
        ln -sfn "$HERMES_HOME" "$HOME/.hermes"
    fi
elif [[ -e "$HOME/.hermes" ]]; then
    err "~/.hermes exists and is not a symlink. Backing up and replacing."
    mv "$HOME/.hermes" "$HOME/.hermes.bak.$(date +%s)"
    ln -sfn "$HERMES_HOME" "$HOME/.hermes"
    ok "~/.hermes symlinked to $HERMES_HOME"
else
    ln -sfn "$HERMES_HOME" "$HOME/.hermes"
    ok "~/.hermes symlinked to $HERMES_HOME"
fi

# 1. Clone repos if not present
if [[ ! -d "$PROJECT_ROOT/external/Hermes-Agent/.git" ]]; then
    log "Cloning Hermes-Agent..."
    git clone https://github.com/NousResearch/Hermes-Agent.git "$PROJECT_ROOT/external/Hermes-Agent"
    cd "$PROJECT_ROOT/external/Hermes-Agent"
    git checkout 5ecc07986f46463ca3096679b03a46402eb19cee
    ok "Hermes-Agent cloned at pinned commit"
else
    ok "Hermes-Agent already cloned"
fi

if [[ ! -d "$PROJECT_ROOT/external/OpenMontage/.git" ]]; then
    log "Cloning OpenMontage..."
    git clone https://github.com/calesthio/OpenMontage.git "$PROJECT_ROOT/external/OpenMontage"
    cd "$PROJECT_ROOT/external/OpenMontage"
    git checkout f633b5f428b9be9a2afecba851dfddd101619756
    ok "OpenMontage cloned at pinned commit"
else
    ok "OpenMontage already cloned"
fi

# 2. Install Hermes
cd "$PROJECT_ROOT/external/Hermes-Agent"
if command -v hermes &>/dev/null; then
    ok "Hermes CLI already available"
else
    log "Running setup-hermes.sh..."
    bash setup-hermes.sh
    ok "Hermes installed"
fi

# 3. Create football-emotion profile
if hermes profile list 2>/dev/null | grep -q "football-emotion"; then
    ok "Profile 'football-emotion' already exists"
else
    log "Creating Hermes profile 'football-emotion'..."
    HERMES_HOME="$HERMES_HOME" hermes profile create football-emotion --clone-all
    ok "Profile 'football-emotion' created"
fi

# 4. Install OpenMontage (FFmpeg-only)
cd "$PROJECT_ROOT/external/OpenMontage"
if [[ -d ".venv" ]] && [[ -x ".venv/bin/python" ]]; then
    ok "OpenMontage venv exists"
else
    log "Running 'make install' (FFmpeg-only, no Remotion/HyperFrames)..."
    make install
    ok "OpenMontage Python deps installed"
fi

# 5. Install skills
log "Installing Football Emotion V7 skills..."
"$SCRIPT_DIR/install_skills.sh"

# 6. Validate
log "Validating setup..."
"$SCRIPT_DIR/validate_setup.py"

ok "Kaggle bootstrap complete!"
echo ""
echo "Environment variables set:"
echo "  HERMES_HOME=$HERMES_HOME"
echo "  OPENMONTAGE_PROJECTS_DIR=$OPENMONTAGE_PROJECTS_DIR"
echo ""
echo "To use in notebook cells:"
echo "  import os; os.environ['HERMES_HOME'] = '/kaggle/working/.hermes'"
echo "  os.environ['OPENMONTAGE_PROJECTS_DIR'] = '/kaggle/working/projects'"