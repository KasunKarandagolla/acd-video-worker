#!/usr/bin/env bash
set -e

REPORT="state/runs/environment_check.md"
mkdir -p "$(dirname "$REPORT")"

echo "# Environment Check Report" > "$REPORT"
echo "Generated: $(date -u '+%Y-%m-%dT%H:%M:%SZ')" >> "$REPORT"
echo "" >> "$REPORT"

failures=0

check_cmd() {
    local cmd=$1
    local label=$2
    local required=$3
    if command -v "$cmd" &>/dev/null; then
        local ver
        ver=$($cmd --version 2>&1 | head -1 || true)
        echo "  - $label: $ver" >> "$REPORT"
        echo "[OK] $label found"
    else
        if [ "$required" = "required" ]; then
            echo "  - $label: NOT FOUND (REQUIRED)" >> "$REPORT"
            echo "[FAIL] $label not found (required)"
            failures=$((failures + 1))
        else
            echo "  - $label: NOT FOUND (optional)" >> "$REPORT"
            echo "[WARN] $label not found (optional)"
        fi
    fi
}

check_pip_pkg() {
    local pkg=$1
    local required=$2
    if python3 -c "import $pkg" 2>/dev/null; then
        echo "  - python package $pkg: found" >> "$REPORT"
        echo "[OK] python package $pkg found"
    else
        if [ "$required" = "required" ]; then
            echo "  - python package $pkg: NOT FOUND (REQUIRED)" >> "$REPORT"
            echo "[FAIL] python package $pkg not found (required)"
            failures=$((failures + 1))
        else
            echo "  - python package $pkg: NOT FOUND (optional, installing...)" >> "$REPORT"
            echo "[WARN] python package $pkg not found, installing..."
            pip3 install "$pkg" 2>&1 || true
        fi
    fi
}

echo "## Required System Tools" >> "$REPORT"
check_cmd "python3" "Python 3" "required"
check_cmd "git" "Git" "required"
check_cmd "ffmpeg" "FFmpeg" "required"
check_cmd "unzip" "Unzip" "required"

echo "" >> "$REPORT"
echo "## Optional System Tools" >> "$REPORT"
check_cmd "node" "Node.js" "optional"
check_cmd "npm" "npm" "optional"

echo "" >> "$REPORT"
echo "## Python Packages" >> "$REPORT"
check_pip_pkg "requests" "required"
check_pip_pkg "yaml" "required"

echo "" >> "$REPORT"
echo "## yt-dlp" >> "$REPORT"
if command -v yt-dlp &>/dev/null; then
    echo "  - yt-dlp: found ($(yt-dlp --version 2>&1 | head -1))" >> "$REPORT"
    echo "[OK] yt-dlp found"
elif python3 -c "import yt_dlp" 2>/dev/null; then
    echo "  - yt-dlp: found as python module" >> "$REPORT"
    echo "[OK] yt-dlp found as python module"
else
    echo "  - yt-dlp: NOT FOUND, installing with pip..." >> "$REPORT"
    echo "[WARN] yt-dlp not found, installing..."
    pip3 install yt-dlp 2>&1 || true
fi

echo "" >> "$REPORT"
echo "## Result" >> "$REPORT"
if [ "$failures" -eq 0 ]; then
    echo "All required checks passed." >> "$REPORT"
    echo "[PASS] All required checks passed"
else
    echo "$failures required check(s) failed." >> "$REPORT"
    echo "[FAIL] $failures required check(s) failed"
fi

exit "$failures"
