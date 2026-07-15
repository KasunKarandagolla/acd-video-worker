#!/usr/bin/env bash
# One restart-safe Kaggle entrypoint: exact checkout -> bootstrap -> certificate.

set -euo pipefail

REPO_URL="${ACD_REPO_URL:-https://github.com/KasunKarandagolla/acd-video-worker.git}"
REPO_BRANCH="${ACD_REPO_BRANCH:-codex-thin-orchestration-final}"
REPO_DIR="${ACD_REPO_DIR:-/kaggle/working/acd-video-worker-thin-smoke}"
EXPECTED_COMMIT="${ACD_EXPECTED_COMMIT:-}"

if [[ -d "$REPO_DIR/.git" ]]; then
    if [[ -n "$(git -C "$REPO_DIR" status --porcelain)" ]]; then
        echo "Refusing to update a dirty Kaggle checkout: $REPO_DIR" >&2
        exit 2
    fi
    git -C "$REPO_DIR" fetch origin "$REPO_BRANCH:refs/remotes/origin/$REPO_BRANCH"
    if git -C "$REPO_DIR" show-ref --verify --quiet "refs/heads/$REPO_BRANCH"; then
        git -C "$REPO_DIR" switch "$REPO_BRANCH"
    else
        git -C "$REPO_DIR" switch --track -c "$REPO_BRANCH" "origin/$REPO_BRANCH"
    fi
    git -C "$REPO_DIR" merge --ff-only "origin/$REPO_BRANCH"
else
    if [[ -e "$REPO_DIR" && ! -d "$REPO_DIR" ]]; then
        echo "Refusing to replace a non-directory path: $REPO_DIR" >&2
        exit 2
    fi
    if [[ -d "$REPO_DIR" && -n "$(find "$REPO_DIR" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
        echo "Refusing to replace a non-repository directory: $REPO_DIR" >&2
        exit 2
    fi
    git clone --branch "$REPO_BRANCH" --single-branch "$REPO_URL" "$REPO_DIR"
fi

ACTIVE_COMMIT="$(git -C "$REPO_DIR" rev-parse HEAD)"
if [[ -n "$EXPECTED_COMMIT" && "$ACTIVE_COMMIT" != "$EXPECTED_COMMIT" ]]; then
    echo "Kaggle checkout mismatch: expected $EXPECTED_COMMIT, got $ACTIVE_COMMIT" >&2
    exit 2
fi

echo "ACTIVE_COMMIT=$ACTIVE_COMMIT"
exec bash "$REPO_DIR/bootstrap/bootstrap_kaggle.sh"
