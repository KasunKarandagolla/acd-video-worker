#!/usr/bin/env bash
# Install Football Emotion V7 skills to Hermes profile

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="$PROJECT_ROOT/bootstrap"

log() { echo -e "\033[1;33m→\033[0m $*"; }
ok() { echo -e "\033[0;32m✓\033[0m $*"; }
err() { echo -e "\033[0;31m✗\033[0m $*" >&2; }

# Use canonical repo-owned skill folder
CANONICAL_SKILLS="$PROJECT_ROOT/skills/football-emotion-video"

# Determine the exact named-profile skills directory used by `hermes -p`.
HERMES_ROOT="${HERMES_ROOT:-${HERMES_HOME:-$HOME/.hermes}}"
HERMES_PROFILE="${HERMES_PROFILE:-football-emotion}"
if [[ "$(basename "$(dirname "$HERMES_ROOT")")" == "profiles" ]]; then
    PROFILE_HOME="$HERMES_ROOT"
else
    PROFILE_HOME="$HERMES_ROOT/profiles/$HERMES_PROFILE"
fi
PROFILE_SKILLS_DIR="$PROFILE_HOME/skills/football-emotion-video"
PROFILE_PLUGINS_DIR="$PROFILE_HOME/plugins"

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

# 2. Validate canonical skills before installing. Installation never rewrites
# the finalized Football Emotion Skill System.
log "Validating canonical skills..."
if python3 "$CANONICAL_SKILLS/tools/validate_skill_system.py" "$CANONICAL_SKILLS" 2>&1 | grep -q "PASSED"; then
    ok "Canonical skills validation PASSED"
else
    err "Canonical skills validation FAILED"
    exit 1
fi

# 3. Install to Hermes profile
log "Installing to Hermes profile: $PROFILE_SKILLS_DIR"
mkdir -p "$PROFILE_SKILLS_DIR"
rsync -a --delete "$CANONICAL_SKILLS/" "$PROFILE_SKILLS_DIR/"
ok "Skills synced to Hermes profile"

# Hermes skill_view resolves linked reference files from the individual skill
# directory.  The canonical Football Emotion package intentionally keeps its
# shared references at package scope, so install read-only runtime mirrors
# without rewriting or reducing the canonical skill system.
BRIDGE_RUNTIME_REFS="$PROFILE_SKILLS_DIR/skills/hermes-openmontage-repo-bridge/references"
mkdir -p "$BRIDGE_RUNTIME_REFS"
rsync -a "$CANONICAL_SKILLS/shared/references/repo-bridge/" "$BRIDGE_RUNTIME_REFS/"
cp "$CANONICAL_SKILLS/shared/contracts/openmontage-artifact-bridge.md" \
   "$BRIDGE_RUNTIME_REFS/openmontage-artifact-bridge.md"
ok "Bridge reference mirrors installed for Hermes skill_view"

# Install the supported Hermes plugin that exposes the pinned OpenMontage
# authoring/tool surface directly.  This removes the need for the agent to
# improvise shell commands or import OpenMontage from Hermes' Python sandbox.
mkdir -p "$PROFILE_PLUGINS_DIR/acd-openmontage"
rsync -a --delete "$PROJECT_ROOT/plugins/acd-openmontage/" \
  "$PROFILE_PLUGINS_DIR/acd-openmontage/"
ok "ACD OpenMontage Hermes plugin installed"

# 4. Validate installed skills
log "Validating installed skills..."
if python3 "$PROFILE_SKILLS_DIR/tools/validate_skill_system.py" "$PROFILE_SKILLS_DIR" 2>&1 | grep -q "PASSED"; then
    ok "Installed skills validation PASSED"
else
    err "Installed skills validation FAILED"
    exit 1
fi

ok "Skills installation complete"
