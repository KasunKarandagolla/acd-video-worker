#!/usr/bin/env bash
# Install Hermes at pinned commit

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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
    if bash setup-hermes.sh; then
        ok "Hermes installed"
    elif [[ -x "$HOME/.local/bin/hermes" ]]; then
        # The pinned upstream installer can finish successfully (venv and CLI
        # symlink created) but return non-zero in a fresh non-interactive
        # Kaggle shell while attempting shell-profile follow-up work.
        ok "Hermes installed; ignoring post-install shell-profile status"
    else
        err "Hermes setup failed before creating the CLI"
        exit 1
    fi
    hash -r
fi

# Verify
hermes --version && ok "Hermes version: $(hermes --version)"

# The pinned Hermes web tool uses its bundled DuckDuckGo provider as the
# zero-key research path, but ddgs is an optional dependency.  Install it into
# Hermes' own venv so OpenMontage research stages never fall back to curl,
# package installation, or an unavailable Python import during production.
DDGS_VERSION="${ACD_DDGS_VERSION:-9.14.4}"
if ! "$HERMES_DIR/venv/bin/python" -c \
    "import importlib.metadata as m; assert m.version('ddgs') == '$DDGS_VERSION'" \
    >/dev/null 2>&1; then
    log "Installing Hermes zero-key DDGS research provider"
    uv pip install --python "$HERMES_DIR/venv/bin/python" "ddgs==$DDGS_VERSION"
fi
"$HERMES_DIR/venv/bin/python" -c \
    "import importlib.metadata as m; assert m.version('ddgs') == '$DDGS_VERSION'" \
    && ok "Hermes DDGS research provider available ($DDGS_VERSION)"
