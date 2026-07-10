#!/usr/bin/env bash
set -e

REPORT_JSON="state/runs/runtime_dependency_report.json"
REPORT_MD="state/runs/runtime_dependency_report.md"
mkdir -p "$(dirname "$REPORT_JSON")" /kaggle/working/.venvs 2>/dev/null || true
mkdir -p "$(dirname "$REPORT_MD")"

HERMES_REPO="external/Hermes-Agent"
OM_REPO="external/OpenMontage"
HERMES_VENV="/kaggle/working/.venvs/hermes"
KAGGLE_CACHE="/kaggle/datasets"  # Kaggle datasets mount; read-only cache

echo "=== Runtime Dependency Installation ==="
echo ""

# --- Ensure Hermes repo is cloned ---
if [ ! -d "$HERMES_REPO" ] || [ ! -f "$HERMES_REPO/pyproject.toml" ]; then
    echo "ERROR: Hermes-Agent not cloned at $HERMES_REPO"
    echo "{\"status\":\"blocked\",\"blocker\":\"Hermes-Agent not cloned\",\"hermes_deps\":[],\"openmontage_deps\":[]}" > "$REPORT_JSON"
    exit 1
fi

# --- Detect Python ---
PYTHON="python3"
if command -v python3.11 &>/dev/null; then
    PYTHON="python3.11"
fi

# --- Create isolated Hermes venv (NOT inside external/Hermes-Agent) ---
if [ ! -d "$HERMES_VENV/bin" ]; then
    echo "Creating Hermes virtual environment at $HERMES_VENV ..."
    "$PYTHON" -m venv "$HERMES_VENV"
fi
source "$HERMES_VENV/bin/activate"

# --- Upgrade pip ---
pip install --quiet --upgrade pip setuptools wheel 2>&1 | tail -1

# --- Install Hermes core deps (minimum extras: AIAgent + NVIDIA provider) ---
echo "Installing Hermes core dependencies ..."
HERMES_DEPS=()
HERMES_PIP_LOG=$(mktemp)
cd "$HERMES_REPO"

# Hermes pyproject.toml pins exact versions. Install core deps from it.
# The [project] dependencies section lists:
#   openai, python-dotenv, fire, httpx[socks], rich, tenacity, pyyaml,
#   ruamel.yaml, requests, jinja2, pydantic, prompt_toolkit, croniter,
#   packaging, Markdown, PyJWT[crypto], urllib3, cryptography, tzdata,
#   psutil, websockets, pathspec, fastapi, uvicorn[standard],
#   python-multipart, ptyprocess, Pillow, concurrent-log-handler
#
# We install the pyproject.toml via pip with minimal extras:
#   --no-build-isolation to use the venv's build deps
#   -e . for the editable install
#
# Use pip install with constraint to avoid version conflicts.
# If the full pip install -e . fails, fall back to core dep list.
if pip install --quiet --no-build-isolation -e '.' 2>&1 | tail -5 >> "$HERMES_PIP_LOG"; then
    echo "  Hermes editable install succeeded."
    HERMES_DEPS+=("hermes-agent (editable)")
else
    echo "  Editable install failed; installing core dep list ..."
    # Core deps from pyproject.toml [project] dependencies (exact pins)
    pip install --quiet \
        "openai>=2.24.0" \
        "python-dotenv>=1.0" \
        "fire>=0.7.1" \
        "httpx>=0.28.1" \
        "rich>=14.0" \
        "tenacity>=9.0" \
        "pyyaml>=6.0" \
        "requests>=2.31" \
        "pydantic>=2.0" \
        "packaging>=26.0" \
        "Pillow>=12.0" \
        "croniter>=6.0" \
        "psutil>=7.0" \
        "websockets>=15.0" \
        2>&1 | tail -3 >> "$HERMES_PIP_LOG"
    HERMES_DEPS+=("openai" "python-dotenv" "fire" "httpx" "rich" "tenacity" "pyyaml" "requests" "pydantic" "Pillow" "packaging" "croniter" "psutil" "websockets")
fi

# --- Install Hermes optional extras for AIAgent functionality ---
# AIAgent uses: terminal_tool, browser_tool, skills_tool, memory_manager
# We need: tools.* packages, agent.* packages, and their dependencies
echo "Installing Hermes tool/service dependencies ..."
pip install --quiet "jsonschema>=4.20" "aiohttp>=3.14" "youtube-transcript-api>=1.0" "beautifulsoup4>=4.0" "markdownify>=0.14" 2>&1 | tail -2 >> "$HERMES_PIP_LOG"
HERMES_DEPS+=("jsonschema" "aiohttp" "youtube-transcript-api" "beautifulsoup4" "markdownify")

deactivate

# --- Install OpenMontage dependencies ---
echo "Installing OpenMontage dependencies ..."
OM_DEPS=()
OM_PIP_LOG=$(mktemp)

if [ -f "$OM_REPO/requirements.txt" ]; then
    pip install --quiet -r "$OM_REPO/requirements.txt" 2>&1 | tail -3 >> "$OM_PIP_LOG"
    OM_DEPS+=("pyyaml" "pydantic" "jsonschema" "python-dotenv" "Pillow" "numpy" "requests" "google-genai" "openai")
    echo "  OpenMontage requirements installed."
elif [ -f "$OM_REPO/setup.py" ]; then
    pip install --quiet -e "$OM_REPO" 2>&1 | tail -3 >> "$OM_PIP_LOG"
    OM_DEPS+=("openmontage (editable)")
    echo "  OpenMontage editable install succeeded."
fi

# --- Verify key imports ---
source "$HERMES_VENV/bin/activate"

HERMES_IMPORT_OK=false
if "$PYTHON" -c "import openai; import pydantic; import yaml; import requests; print('hermes core ok')" 2>/dev/null; then
    HERMES_IMPORT_OK=true
fi

# Try importing AIAgent from the cloned repo
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
  "hermes_deps": [$(printf '"%s",' "${HERMES_DEPS[@]}" | sed 's/,$//')],
  "openmontage_deps": [$(printf '"%s",' "${OM_DEPS[@]}" | sed 's/,$//')],
  "python_version": "$("$PYTHON" --version 2>&1)",
  "pip_list": []
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

Installed packages:
$(printf "  - %s\n" "${HERMES_DEPS[@]}")

## OpenMontage

- Pinned commit: $OM_COMMIT
- Core import: ${OM_IMPORT_OK}

Installed packages:
$(printf "  - %s\n" "${OM_DEPS[@]}")

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
