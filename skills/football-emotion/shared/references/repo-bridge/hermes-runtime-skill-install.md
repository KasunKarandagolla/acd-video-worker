# Hermes Runtime Skill Install and Use Contract

This reference keeps the package aligned with the confirmed Hermes repo: `NousResearch/Hermes-Agent`.

## What Hermes contributes

Hermes is the reasoning, skill, tool, memory, automation, and session-recall host. This football-emotion package must use Hermes as an orchestration surface, not as a video renderer.

Hermes-facing responsibilities:

1. Load and trigger `SKILL.md` files from an installed skill folder.
2. Keep the LLM decision loop grounded in the correct skill at each stage.
3. Call local tools, repo scripts, web/search tools, and OpenMontage commands when available.
4. Store reusable lessons after each completed or failed production through `hermes-football-memory-learning`.
5. Preserve user preferences and previous project outcomes without storing unverified legal/current-event claims as truth.

## Install locations

Preferred project-local install:

```text
/home/kasun/Music/Director/Hermes-Agent/optional-skills/creative/football-emotion-video/
```

Portable user install:

```text
~/.hermes/skills/football-emotion-video/
```

Use the path the installed Hermes runtime actually supports. Do not modify Hermes core files unless the user explicitly asks.

## Skill shape

Each skill remains a folder containing `SKILL.md`. Optional `references/`, `scripts/`, `templates/`, and `assets/` folders may be used when the skill needs local supporting material.

This package follows the same progressive-disclosure principle: the top-level skill file should be enough to trigger and route the task; detailed reasoning lives in shared references and is loaded only when needed.

## Hermes memory discipline

After a real run, store only durable reusable lessons, not project noise. Store:

- emotional question and story structure that worked
- chosen OpenMontage pipeline and render runtime
- tool capability envelope and degraded/blocked capabilities
- source types that worked or failed
- license outcomes and rights caveats
- clip patterns that retained emotional value
- visual/audio/QA problems and fixes
- final result status and project record path

Do not store:

- exact scores/timestamps from current events unless verified
- legal-safety claims for third-party match footage
- hallucinated performance metrics
- complete clip lists, source dumps, or raw catalog rows

## Subagent / parallel work boundary

Hermes may delegate parallel tasks, but each subagent must receive the same gates:

- repo setup status
- match fact lock when current events are involved
- OpenMontage schema lock before native operations
- license and rights checks before asset use
- fact provenance labels on exact claims

No subagent is allowed to bypass the parent pipeline route.
