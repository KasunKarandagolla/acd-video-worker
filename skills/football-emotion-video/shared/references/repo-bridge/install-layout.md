# Install Layout — Final Local Setup

Expected root:

```text
/home/kasun/Music/Director/
├── Hermes-Agent/
├── OpenMontage/
└── football_emotion_skill_system_v4_repo_bridge/
```

## Clone commands

```bash
cd /home/kasun/Music/Director
git clone https://github.com/NousResearch/Hermes-Agent.git Hermes-Agent
git clone https://github.com/calesthio/OpenMontage.git OpenMontage
```

## OpenMontage setup

```bash
cd /home/kasun/Music/Director/OpenMontage
make setup
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu_summary(), indent=2))"
```

## Hermes setup

```bash
cd /home/kasun/Music/Director/Hermes-Agent
# Use upstream README/setup instructions for the current commit.
hermes setup
hermes doctor
```

## Skill placement recommendation

Keep the full package outside both repos first:

```text
/home/kasun/Music/Director/football_emotion_skill_system_v4_repo_bridge/
```

Then expose/copy only `skills/` to Hermes if needed, and expose `shared/references/repo-bridge/` to the coding agent as project context.

Do not overwrite OpenMontage's own `skills/pipelines/` director skills. The bridge supplements them.
