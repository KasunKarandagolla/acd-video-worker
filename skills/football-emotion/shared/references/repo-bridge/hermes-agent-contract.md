# Hermes Agent Contract for This Skill System

Use this reference when the agent is running inside or alongside `NousResearch/Hermes-Agent`.

## Hermes responsibilities

Hermes is the **reasoning and memory host**:

1. Interpret the user's creative/video request.
2. Trigger the correct SKILL.md instructions.
3. Run the editorial reasoning loop.
4. Delegate tool work through available tools or repo commands.
5. Persist useful lessons to memory after each video.
6. Remember user preferences, winning structures, failed prompts, and asset decisions.

## Confirmed Hermes repo properties to respect

From the upstream repo structure and README, Hermes includes `skills/`, `optional-skills/`, `tools/`, `providers/`, `agent/`, `hermes_cli/`, `gateway/`, `mcp_serve.py`, `trajectory_compressor.py`, and CLI commands such as `hermes`, `hermes model`, `hermes tools`, `hermes setup`, `hermes doctor`, and `/skills`.

## Installation stance

Recommended install path for this package:

```text
/home/kasun/Music/Director/Hermes-Agent/optional-skills/creative/football-emotion-video/
```

Reason: this is a domain-specific creative skill system, not a core Hermes skill. Keeping it under `optional-skills/creative/` avoids modifying Hermes core behavior.

Alternative portable install:

```text
~/.hermes/skills/football-emotion-video/
```

Use the path Hermes actually supports in the installed environment. Do not assume one path if Hermes config says otherwise.

## Hermes memory update rule

After every production, call `hermes-football-memory-learning` and record:

- brief and emotional question
- chosen OpenMontage pipeline
- tool capability envelope
- sources that worked / failed
- music/SFX decisions and license outcomes
- clip types that retained emotional value
- visual cohesion tier
- assembly/QA problems
- final outcome and reusable lesson

Do not store unverified legal claims as truth. Store them as candidate references with verification status.
