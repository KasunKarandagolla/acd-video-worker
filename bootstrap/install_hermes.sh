#!/usr/bin/env bash
# Install Hermes at pinned commit

set -euo pipefail

PROJECT_ROOT="/home/kasun/Music/Director/acd-video-worker"
SCRIPT_DIR="$PROJECT_ROOT/bootstrap"

log() { echo -e "\033[1;33m→\033[0m $*"; }
ok() { echo -e "\033[0;32m✓\033[0m $*"; }
err() { echo -e "\033[0;31m✗\033[0m $*" >&2; }

HERMES_DIR="$PROJECT_ROOT/external/Hermes-Agent"
PINNED_COMMIT="5ecc07986f46463ca3096679b03a46402eb19cee"

# 1. Clone if needed
if [[ ! -d "$HERMES_DIR/.git" ]]; then
    log "Cloning Hermes-Agent..."
    git clone https://github.com/NousResearch/Hermes-Agent.git "$HERMES_DIR"
fi

# 2. Checkout pinned commit
cd "$HERMES_DIR"
CURRENT=$(git rev-parse HEAD)
if [[ "$CURRENT" != "$PINNED_COMMIT" ]]; then
    log "Checking out pinned commit $PINNED_COMMIT..."
    git fetch origin
    git checkout "$PINNED_COMMIT"
    ok "Hermes-Agent at pinned commit"
else
    ok "Hermes-Agent already at pinned commit"
fi

# 3. Run setup-hermes.sh
if command -v hermes &>/dev/null; then
    ok "Hermes CLI already in PATH"
else
    log "Running setup-hermes.sh..."
    bash setup-hermes.sh
    ok "Hermes installed"
fi

# Verify
hermes --version && ok "Hermes version: $(hermes --version)"