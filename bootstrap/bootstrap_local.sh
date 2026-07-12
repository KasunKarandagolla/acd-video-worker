#!/usr/bin/env bash
# bootstrap/bootstrap_local.sh
# Reproducible local bootstrap for AI Creative Director Football Video System
# Safe to rerun. Detects existing installations.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${CYAN}→${NC} $*"; }
ok() { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
err() { echo -e "${RED}✗${NC} $*"; }

# Load pinned commits
UPSTREAM_LOCK="$PROJECT_ROOT/docs/upstream-lock.json"
if [[ ! -f "$UPSTREAM_LOCK" ]]; then
    err "upstream-lock.json not found at $UPSTREAM_LOCK"
    exit 1
fi

HERMES_COMMIT=$(jq -r '.hermes_agent.commit' "$UPSTREAM_LOCK")
OPENMONTAGE_COMMIT=$(jq -r '.openmontage.commit' "$UPSTREAM_LOCK")

log "Project root: $PROJECT_ROOT"
log "Hermes commit: $HERMES_COMMIT"
log "OpenMontage commit: $OPENMONTAGE_COMMIT"
python3 -m pip install -r "$PROJECT_ROOT/requirements.txt"

# 1. Clone/verify Hermes
log "Setting up Hermes-Agent..."
if [[ -d "$PROJECT_ROOT/external/Hermes-Agent/.git" ]]; then
    cd "$PROJECT_ROOT/external/Hermes-Agent"
    CURRENT=$(git rev-parse HEAD)
    if [[ "$CURRENT" == "$HERMES_COMMIT" ]]; then
        ok "Hermes-Agent already at pinned commit"
    else
        log "Updating Hermes-Agent to pinned commit..."
        git fetch origin
        git checkout "$HERMES_COMMIT"
        ok "Hermes-Agent updated"
    fi
else
    log "Cloning Hermes-Agent..."
    git clone https://github.com/NousResearch/Hermes-Agent.git "$PROJECT_ROOT/external/Hermes-Agent"
    cd "$PROJECT_ROOT/external/Hermes-Agent"
    git checkout "$HERMES_COMMIT"
    ok "Hermes-Agent cloned at pinned commit"
fi

# 2. Clone/verify OpenMontage
log "Setting up OpenMontage..."
if [[ -d "$PROJECT_ROOT/external/OpenMontage/.git" ]]; then
    cd "$PROJECT_ROOT/external/OpenMontage"
    CURRENT=$(git rev-parse HEAD)
    if [[ "$CURRENT" == "$OPENMONTAGE_COMMIT" ]]; then
        ok "OpenMontage already at pinned commit"
    else
        log "Updating OpenMontage to pinned commit..."
        git fetch origin
        git checkout "$OPENMONTAGE_COMMIT"
        ok "OpenMontage updated"
    fi
else
    log "Cloning OpenMontage..."
    git clone https://github.com/calesthio/OpenMontage.git "$PROJECT_ROOT/external/OpenMontage"
    cd "$PROJECT_ROOT/external/OpenMontage"
    git checkout "$OPENMONTAGE_COMMIT"
    ok "OpenMontage cloned at pinned commit"
fi

# 3. Install Hermes
log "Installing Hermes..."
cd "$PROJECT_ROOT/external/Hermes-Agent"
if [[ -f "$HOME/.local/bin/hermes" ]] && command -v hermes &>/dev/null; then
    ok "Hermes CLI already installed"
else
    log "Running setup-hermes.sh..."
    bash setup-hermes.sh
    ok "Hermes installed"
fi

# 4. Create football-emotion profile
log "Creating Hermes profile 'football-emotion'..."
if hermes profile list 2>/dev/null | grep -q "football-emotion"; then
    ok "Profile 'football-emotion' already exists"
else
    hermes profile create football-emotion --clone-all
    ok "Profile 'football-emotion' created"
fi

# 5. Install OpenMontage (FFmpeg-only for local dev too, Remotion optional)
log "Installing OpenMontage (FFmpeg-only)..."
cd "$PROJECT_ROOT/external/OpenMontage"
if [[ -d ".venv" ]] && [[ -x ".venv/bin/python" ]]; then
    ok "OpenMontage venv exists"
else
    log "Running 'make install' (Python deps only, no Remotion/HyperFrames)..."
    make install
    ok "OpenMontage Python deps installed"
fi
"$PROJECT_ROOT/external/OpenMontage/.venv/bin/python" -m pip install -r "$PROJECT_ROOT/requirements.txt"

# Configure a free endpoint when LLM_* values are present; otherwise preserve
# the profile and report the exact remaining manual setup.
python3 "$SCRIPT_DIR/configure_hermes_profile.py" || true

# 6. Install skills
log "Installing Football Emotion V7 skills..."
"$SCRIPT_DIR/install_skills.sh"

# 7. Validate
log "Validating setup..."
"$SCRIPT_DIR/validate_setup.py"

ok "Local bootstrap complete!"
echo ""
echo "Next steps:"
echo "  hermes -p football-emotion chat -q \"hello\""
echo "  hermes -p football-emotion skills list"
