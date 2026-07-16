# Kaggle Final Production Runbook

These cells are restart-safe. A restarted Kaggle kernel has an empty
`/kaggle/working`, so always run them from the top. Do not paste log output into
a Python cell.

## 1. Load the existing Kaggle secret

Run as a Python cell:

```python
import os
from kaggle_secrets import UserSecretsClient

secrets = UserSecretsClient()
os.environ["LLM_API_KEY"] = secrets.get_secret("LLM_API_KEY")
os.environ["LLM_BASE_URL"] = "https://integrate.api.nvidia.com/v1"
os.environ["LLM_MODEL"] = "nvidia/nemotron-3-ultra-550b-a55b"
os.environ["ACD_HERMES_MODEL_OVERRIDE"] = os.environ["LLM_MODEL"]

print("MODEL_SECRET_READY=1")
```

## 2. Clone/update and bootstrap

Run as a Bash cell. It works whether the repository exists or not.

```bash
%%bash
set -euo pipefail

REPO=/kaggle/working/acd-video-worker-thin-smoke
BRANCH=codex-thin-orchestration-final

if [[ ! -d "$REPO/.git" ]]; then
  git clone --branch "$BRANCH" --single-branch \
    https://github.com/KasunKarandagolla/acd-video-worker.git "$REPO"
else
  git -C "$REPO" pull --ff-only origin "$BRANCH"
fi

export PATH="$HOME/.local/bin:$PATH"
export HERMES_HOME=/kaggle/working/.hermes
export HERMES_PROFILE=football-emotion
export OPENMONTAGE_ROOT="$REPO/external/OpenMontage"

cd "$REPO"
echo "ACTIVE_COMMIT=$(git rev-parse HEAD)"
bash bootstrap/bootstrap_kaggle.sh
```

The doctor must show `failed: 0`, with only optional Discord allowed to remain
blocked. It now verifies the exact pinned Hermes request, normalized-response
and real tool-callback surfaces used by production.

## 3. Native runtime canary

This does not call the language model. It verifies the deterministic
OpenMontage/Remotion/render/review/delivery path.

```bash
%%bash
set -euo pipefail

REPO=/kaggle/working/acd-video-worker-thin-smoke
export OPENMONTAGE_ROOT="$REPO/external/OpenMontage"
export OPENMONTAGE_PYTHON="$OPENMONTAGE_ROOT/.venv/bin/python"

rm -rf /kaggle/working/acd-native-contract-canary
cd "$REPO"
PYTHONPATH=src python3 scripts/run_native_contract_canary.py \
  --project-dir /kaggle/working/acd-native-contract-canary \
  --openmontage-root "$OPENMONTAGE_ROOT" \
  --openmontage-python "$OPENMONTAGE_PYTHON"
```

The final object must contain `"valid": true` and a nonblank, nonfrozen media
validation result.

## 4. Fresh production smoke

This cell deliberately does not return a nonzero notebook-cell exit. Read
`ACD_EXIT_STATUS`: `0=DELIVERED`, `2=BLOCKED`, `1=FAILED`.

```bash
%%bash
set -uo pipefail

REPO=/kaggle/working/acd-video-worker-thin-smoke
export PATH="$HOME/.local/bin:$PATH"
export HERMES_HOME=/kaggle/working/.hermes
export HERMES_PROFILE=football-emotion
export OPENMONTAGE_ROOT="$REPO/external/OpenMontage"
export OPENMONTAGE_PROJECTS_DIR=/kaggle/working/projects
export ACD_STATE_DIR=/kaggle/working/acd-state/runs

cd "$REPO"
bash bootstrap/run_kaggle_job.sh \
  --json \
  --approve-all-checkpoints \
  --approve-runtime-tuple cinematic,templated,cinematic-trailer,remotion \
  --approve-silence \
  'Create a genuine 12-second 1280x720 football-emotion kinetic teaser titled "90 MINUTES. ONE DREAM." Use the complete Football Emotion Skill System. Use only original animated typography, geometric football-pitch graphics and generated backgrounds. Use OpenMontage native cinematic production, canonical artifacts, ToolRegistry, video_compose, Remotion and native final_review. Remain strictly zero-cost.'
STATUS=$?

echo "ACD_EXIT_STATUS=$STATUS"
```

Do not retry a failed run blindly. A provider throttle/capacity blocker can be
resumed with the same run/session using `--run-id <id> --retry-blocked --json`.
Authentication, tool-protocol and validation failures require correcting the
reported cause first.
