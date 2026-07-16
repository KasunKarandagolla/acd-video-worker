#!/usr/bin/env bash
# Install OpenMontage at pinned commit

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="$PROJECT_ROOT/bootstrap"

log() { echo -e "\033[1;33m→\033[0m $*"; }
ok() { echo -e "\033[0;32m✓\033[0m $*"; }
err() { echo -e "\033[0;31m✗\033[0m $*" >&2; }

OM_DIR="$PROJECT_ROOT/external/OpenMontage"
PINNED_COMMIT="f633b5f428b9be9a2afecba851dfddd101619756"

# 1. Clone if needed
if [[ ! -d "$OM_DIR/.git" ]]; then
    log "Cloning OpenMontage..."
    git clone https://github.com/calesthio/OpenMontage.git "$OM_DIR"
fi

# 2. Checkout pinned commit
cd "$OM_DIR"
CURRENT=$(git rev-parse HEAD)
if [[ "$CURRENT" != "$PINNED_COMMIT" ]]; then
    log "Checking out pinned commit $PINNED_COMMIT..."
    git fetch origin
    git checkout "$PINNED_COMMIT"
    ok "OpenMontage at pinned commit"
else
    ok "OpenMontage already at pinned commit"
fi

# Preserve the upstream pin and apply only the audited compatibility layer.
# The installer refuses to overwrite unexpected local work.
python3 "$PROJECT_ROOT/bootstrap/apply_openmontage_compatibility.py" \
    --worker-root "$PROJECT_ROOT" \
    --openmontage-root "$OM_DIR"

# 3. Install OpenMontage Python dependencies.
if [[ -d ".venv" ]] && [[ -x ".venv/bin/python" ]]; then
    ok "OpenMontage venv exists"
else
    log "Running 'make install' (Python deps only)..."
    make install
    ok "OpenMontage Python deps installed"
fi

if [[ ! -x "$OM_DIR/remotion-composer/node_modules/.bin/remotion" ]]; then
    log "Installing locked Remotion dependencies..."
    npm ci --prefix "$OM_DIR/remotion-composer" --no-audit --no-fund
fi
log "Pre-installing the Remotion browser..."
(cd "$OM_DIR/remotion-composer" && npx --no-install remotion browser ensure)

# 4. Verify tool registry loads
log "Verifying tool registry..."
cd "$OM_DIR"
if .venv/bin/python -c "from tools.tool_registry import registry; registry.discover(); print('OK')" 2>/dev/null; then
    ok "Tool registry loads successfully"
else
    err "Tool registry failed to load"
    exit 1
fi

# 5. Verify pipeline loader
if .venv/bin/python -c "
from lib.pipeline_loader import load_pipeline, list_pipelines
p = load_pipeline('documentary-montage')
assert p['name'] == 'documentary-montage'
print('Pipeline OK:', [s['name'] for s in p['stages']])
" 2>/dev/null; then
    ok "documentary-montage pipeline loads"
else
    err "Pipeline load failed"
    exit 1
fi

ok "OpenMontage install complete"
