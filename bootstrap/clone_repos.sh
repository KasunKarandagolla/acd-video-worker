#!/usr/bin/env bash
set -e

mkdir -p external locks

PINNED_FILE="locks/pinned_versions.json"
if [ ! -f "$PINNED_FILE" ]; then
    echo "ERROR: Pinned versions file not found: $PINNED_FILE"
    exit 1
fi

read_pinned_revision() {
    local key="$1"
    python3 -c "
import json
with open('$PINNED_FILE') as f:
    cfg = json.load(f)
print(cfg['$key']['revision'])
"
}

pin_repo() {
    local name="$1"
    local dir="external/$name"
    local key="$2"
    local url="$3"

    local REVISION
    REVISION=$(read_pinned_revision "$key")

    echo "=== $name (pinned to $REVISION) ==="

    if [ -d "$dir/.git" ]; then
        echo "Already cloned, fetching..."
        git -C "$dir" fetch --tags --force origin 2>&1
    else
        echo "Cloning..."
        git clone "$url" "$dir"
    fi

    git -C "$dir" checkout --detach "$REVISION" 2>&1

    local HEAD_REV
    HEAD_REV=$(git -C "$dir" rev-parse HEAD 2>/dev/null || echo "")

    if [ "$HEAD_REV" != "$REVISION" ]; then
        echo "ERROR: $name revision mismatch!"
        echo "  Expected: $REVISION"
        echo "  Got:      $HEAD_REV"
        exit 1
    fi

    echo "$HEAD_REV" > "locks/${name}_PINNED_COMMIT.txt"
    echo "$name pinned commit: $HEAD_REV (verified)"
    echo ""
}

HERMES_URL="https://github.com/NousResearch/Hermes-Agent.git"
OM_URL="https://github.com/calesthio/OpenMontage.git"

pin_repo "Hermes-Agent" "hermes_agent" "$HERMES_URL"
pin_repo "OpenMontage" "open_montage" "$OM_URL"

echo "Clone/update complete."
echo "All repos pinned to their locked revisions."
