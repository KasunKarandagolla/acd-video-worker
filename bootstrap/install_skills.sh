#!/usr/bin/env bash
set -e

SKILL_ZIP="packages/football_emotion_skill_system_v7_final_runtime.zip"
SKILL_DIR="skills/football-emotion"
REPORT="state/runs/skill_install_report.md"
mkdir -p "$(dirname "$REPORT")"

echo "=== Installing Football Emotion Skill System v7 ==="

echo "# Skill Install Report" > "$REPORT"
echo "Generated: $(date -u '+%Y-%m-%dT%H:%M:%SZ')" >> "$REPORT"
echo "" >> "$REPORT"

if [ ! -f "$SKILL_ZIP" ]; then
    echo "ERROR: Skill ZIP not found at $SKILL_ZIP" | tee -a "$REPORT"
    exit 1
fi

echo "Extracting $SKILL_ZIP ..." | tee -a "$REPORT"
TMP_EXTRACT=$(mktemp -d)
unzip -o "$SKILL_ZIP" -d "$TMP_EXTRACT" > /dev/null 2>&1

echo "Detecting ZIP structure..." >> "$REPORT"
INNER_DIR="$TMP_EXTRACT/football_emotion_skill_system_v7_final_runtime"
if [ -d "$INNER_DIR" ]; then
    echo "Detected top-level folder: football_emotion_skill_system_v7_final_runtime" | tee -a "$REPORT"
    SOURCE_DIR="$INNER_DIR"
else
    echo "No extra top-level folder detected." | tee -a "$REPORT"
    SOURCE_DIR="$TMP_EXTRACT"
fi

echo "Removing old skill directory..." | tee -a "$REPORT"
rm -rf "$SKILL_DIR"
mkdir -p "$SKILL_DIR"

echo "Copying extracted contents to $SKILL_DIR ..." | tee -a "$REPORT"
# Use find to copy non-hidden files and directories only
find "$SOURCE_DIR" -mindepth 1 -maxdepth 1 ! -name '.*' -exec cp -r {} "$SKILL_DIR/" \;

rm -rf "$TMP_EXTRACT"

echo "" >> "$REPORT"
echo "Final skill structure:" >> "$REPORT"
ls "$SKILL_DIR" >> "$REPORT"
echo "" >> "$REPORT"

echo "Verifying expected directories..." | tee -a "$REPORT"
for sub in skills shared tools evals; do
    if [ -d "$SKILL_DIR/$sub" ]; then
        echo "  [OK] $sub/ exists" | tee -a "$REPORT"
    else
        echo "  [WARN] $sub/ not found" | tee -a "$REPORT"
    fi
done

if [ -f "$SKILL_DIR/README.md" ]; then
    echo "  [OK] README.md exists" | tee -a "$REPORT"
else
    echo "  [WARN] README.md not found" | tee -a "$REPORT"
fi

echo "" >> "$REPORT"
echo "Running available validators..." | tee -a "$REPORT"

VALIDATORS=(
    "$SKILL_DIR/skills/validate.sh"
    "$SKILL_DIR/validate.sh"
    "$SKILL_DIR/tools/validate.py"
    "$SKILL_DIR/evals/validate.py"
    "$SKILL_DIR/evals/run_validation.py"
)

VALIDATOR_FOUND=false
for validator in "${VALIDATORS[@]}"; do
    if [ -f "$validator" ]; then
        echo "Running validator: $validator" | tee -a "$REPORT"
        if [[ "$validator" == *.sh ]]; then
            bash "$validator" 2>&1 | tee -a "$REPORT" || echo "Validator exited non-zero, continuing..." | tee -a "$REPORT"
        elif [[ "$validator" == *.py ]]; then
            python3 "$validator" 2>&1 | tee -a "$REPORT" || echo "Validator exited non-zero, continuing..." | tee -a "$REPORT"
        fi
        VALIDATOR_FOUND=true
        break
    fi
done

if [ "$VALIDATOR_FOUND" = false ]; then
    echo "  No standalone validators found. This is not necessarily an error." | tee -a "$REPORT"
fi

echo "" >> "$REPORT"
echo "Skill installation complete." >> "$REPORT"
echo "=== Skill installation complete ==="
