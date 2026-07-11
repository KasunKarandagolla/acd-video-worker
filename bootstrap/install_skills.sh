#!/usr/bin/env bash
# Install Football Emotion V7 skills to Hermes profile

set -euo pipefail

PROJECT_ROOT="/home/kasun/Music/Director/acd-video-worker"
SCRIPT_DIR="$PROJECT_ROOT/bootstrap"

log() { echo -e "\033[1;33m→\033[0m $*"; }
ok() { echo -e "\033[0;32m✓\033[0m $*"; }
err() { echo -e "\033[0;31m✗\033[0m $*" >&2; }

# Use canonical repo-owned skill folder
CANONICAL_SKILLS="$PROJECT_ROOT/skills/football-emotion-video"

# Determine Hermes profile skills directory
if [[ -n "${HERMES_HOME:-}" ]]; then
    PROFILE_SKILLS_DIR="$HERMES_HOME/skills/football-emotion-video"
else
    PROFILE_SKILLS_DIR="$HOME/.hermes/profiles/football-emotion/skills/football-emotion-video"
fi

# 1. Ensure canonical skills exist (extracted from ZIP)
if [[ ! -d "$CANONICAL_SKILLS/skills" ]]; then
    log "Extracting V7 skills from ZIP to canonical location..."
    mkdir -p "$CANONICAL_SKILLS"
    unzip -o "$PROJECT_ROOT/packages/football_emotion_skill_system_v7_final_runtime.zip" -d /tmp/v7_extract/
    cp -r /tmp/v7_extract/football_emotion_skill_system_v7_final_runtime/* "$CANONICAL_SKILLS/"
    ok "Canonical skills extracted"
else
    ok "Canonical skills already exist"
fi

# 2. Apply corrections to canonical skills
log "Applying corrections to canonical skills..."
"$SCRIPT_DIR/apply_skill_corrections.sh"
ok "Corrections applied"

# 3. Validate canonical skills before installing
log "Validating canonical skills..."
if python3 "$CANONICAL_SKILLS/tools/validate_skill_system.py" "$CANONICAL_SKILLS" 2>&1 | grep -q "PASSED"; then
    ok "Canonical skills validation PASSED"
else
    err "Canonical skills validation FAILED"
    exit 1
fi

# 4. Install to Hermes profile
log "Installing to Hermes profile: $PROFILE_SKILLS_DIR"
mkdir -p "$PROFILE_SKILLS_DIR"
rsync -a --delete "$CANONICAL_SKILLS/" "$PROFILE_SKILLS_DIR/"
ok "Skills synced to Hermes profile"

# 5. Validate installed skills
log "Validating installed skills..."
if python3 "$PROFILE_SKILLS_DIR/tools/validate_skill_system.py" "$PROFILE_SKILLS_DIR" 2>&1 | grep -q "PASSED"; then
    ok "Installed skills validation PASSED"
else
    err "Installed skills validation FAILED"
    exit 1
fi

ok "Skills installation complete"