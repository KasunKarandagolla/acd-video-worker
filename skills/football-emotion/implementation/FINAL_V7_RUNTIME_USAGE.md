# Final V7 Runtime Usage

## Setup

```bash
cd /home/kasun/Music/Director

git clone https://github.com/NousResearch/Hermes-Agent.git Hermes-Agent
git clone https://github.com/calesthio/OpenMontage.git OpenMontage

cd Hermes-Agent && git rev-parse HEAD > ../HERMES_AGENT_PINNED_COMMIT.txt
cd ../OpenMontage && git rev-parse HEAD > ../OPENMONTAGE_PINNED_COMMIT.txt
```

Install this package into Hermes' optional skills or user skills path according to the installed Hermes config.

## First run rule

Do not start with a creative edit plan. Start with:

1. `hermes-openmontage-repo-bridge`
2. `repo_setup_status`
3. OpenMontage `support_envelope()` / `provider_menu()` discovery
4. selected pipeline manifest inspection
5. `openmontage_schema_lock`
6. match/current-event fact lock if relevant

Only then proceed to brief interpretation and sourcing.

## Simulation rule

If local repos, schemas, or footage are unavailable, output a simulation/hypothesis plan only. Do not invent native OpenMontage operations.
