#!/usr/bin/env bash
set -e

mkdir -p external locks

echo "=== Cloning/Updating Hermes-Agent ==="
if [ -d "external/Hermes-Agent/.git" ]; then
    echo "Hermes-Agent already cloned, pulling latest..."
    cd external/Hermes-Agent
    git pull --ff-only 2>&1 || echo "WARN: could not fast-forward pull, skipping"
    cd ../..
else
    echo "Cloning Hermes-Agent..."
    git clone https://github.com/NousResearch/Hermes-Agent.git external/Hermes-Agent
fi

HERMES_COMMIT=$(cd external/Hermes-Agent && git rev-parse HEAD 2>/dev/null || echo "unknown")
echo "$HERMES_COMMIT" > locks/HERMES_AGENT_PINNED_COMMIT.txt
echo "Hermes-Agent pinned commit: $HERMES_COMMIT"

echo ""
echo "=== Cloning/Updating OpenMontage ==="
if [ -d "external/OpenMontage/.git" ]; then
    echo "OpenMontage already cloned, pulling latest..."
    cd external/OpenMontage
    git pull --ff-only 2>&1 || echo "WARN: could not fast-forward pull, skipping"
    cd ../..
else
    echo "Cloning OpenMontage..."
    git clone https://github.com/calesthio/OpenMontage.git external/OpenMontage
fi

OPENMONTAGE_COMMIT=$(cd external/OpenMontage && git rev-parse HEAD 2>/dev/null || echo "unknown")
echo "$OPENMONTAGE_COMMIT" > locks/OPENMONTAGE_PINNED_COMMIT.txt
echo "OpenMontage pinned commit: $OPENMONTAGE_COMMIT"

echo ""
echo "Clone/update complete."
echo "Hermes-Agent: $HERMES_COMMIT"
echo "OpenMontage: $OPENMONTAGE_COMMIT"
