#!/usr/bin/env bash
set -e

REPORT_JSON="state/runs/runtime_dependency_report.json"
REPORT_MD="state/runs/runtime_dependency_report.md"
mkdir -p "$(dirname "$REPORT_JSON")" /kaggle/working/.venvs 2>/dev/null || true
mkdir -p "$(dirname "$REPORT_MD")"

HERMES_REPO="external/Hermes-Agent"
OM_REPO="external/OpenMontage"

# Determine venv path (must match install_deps.py logic)
if [ -n "$ACD_HERMES_VENV" ]; then
    HERMES_VENV="$ACD_HERMES_VENV"
elif [ -n "$KAGGLE_KERNEL_RUN_TYPE" ] || [ -d "/kaggle/working" ]; then
    HERMES_VENV="/kaggle/working/.venvs/hermes"
else
    HERMES_VENV=".runtime/venvs/hermes"
fi

echo "=== Runtime Dependency Installation ==="
echo ""

# --- Detect Python ---
PYTHON="python3"
if command -v python3.11 &>/dev/null; then
    PYTHON="python3.11"
fi

# --- Delegate to the corrected Python installer ---
# Handles: Checking virtualenv, Creating Hermes environment,
# Verifying environment pip, Installing Hermes dependencies,
# Installing required OpenMontage dependencies
echo "Checking virtualenv"
python3 scripts/install_deps.py

# --- Source venv for verification ---
if [ -f "$HERMES_VENV/bin/activate" ]; then
    source "$HERMES_VENV/bin/activate"
else
    echo "ERROR: Hermes venv not found at $HERMES_VENV"
    exit 1
fi

# --- Verify key imports ---
HERMES_IMPORT_OK=false
if "$PYTHON" -c "import openai; import pydantic; import yaml; import requests; print('hermes core ok')" 2>/dev/null; then
    HERMES_IMPORT_OK=true
fi

AIAgent_IMPORT_OK=false
if "$PYTHON" -c "import sys; sys.path.insert(0, '$HERMES_REPO'); from run_agent import AIAgent; print('AIAgent ok')" 2>/dev/null; then
    AIAgent_IMPORT_OK=true
fi

OM_IMPORT_OK=false
if "$PYTHON" -c "import yaml; import pydantic; import jsonschema; from pathlib import Path; print('om core ok')" 2>/dev/null; then
    OM_IMPORT_OK=true
fi

deactivate

# --- Write report ---
HERMES_COMMIT=$(cat locks/HERMES_AGENT_PINNED_COMMIT.txt 2>/dev/null || echo "unknown")
OM_COMMIT=$(cat locks/OPENMONTAGE_PINNED_COMMIT.txt 2>/dev/null || echo "unknown")

cat > "$REPORT_JSON" << JSONEOF
{
  "status": "complete",
  "timestamp_utc": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "hermes_venv": "$HERMES_VENV",
  "hermes_commit": "$HERMES_COMMIT",
  "openmontage_commit": "$OM_COMMIT",
  "hermes_import_ok": $HERMES_IMPORT_OK,
  "hermes_aiagent_import_ok": $AIAgent_IMPORT_OK,
  "openmontage_import_ok": $OM_IMPORT_OK,
  "python_version": "$("$PYTHON" --version 2>&1)"
}
JSONEOF

cat > "$REPORT_MD" << MDEOF
# Runtime Dependency Report

Generated: $(date -u '+%Y-%m-%dT%H:%M:%SZ')
Status: Complete

## Hermes-Agent

- VENV: $HERMES_VENV
- Pinned commit: $HERMES_COMMIT
- Core import: ${HERMES_IMPORT_OK}
- AIAgent import: ${AIAgent_IMPORT_OK}

## OpenMontage

- Pinned commit: $OM_COMMIT
- Core import: ${OM_IMPORT_OK}

## Python

- $("$PYTHON" --version 2>&1)
MDEOF

echo ""
echo "Runtime dependency report: $REPORT_JSON"
echo "Hermes AIAgent import: $AIAgent_IMPORT_OK"
echo "OpenMontage import: $OM_IMPORT_OK"
echo ""

if [ "$AIAgent_IMPORT_OK" = false ]; then
    echo "WARNING: Hermes AIAgent import failed. Skills will not load."
fi

echo "Dependency installation complete"
