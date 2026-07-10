# Integration Gap Report

## Hermes-Agent Gaps

| Requirement | Status | Evidence |
|------------|--------|----------|
| Hermes CLI entrypoint | IDENTIFIED | `cli.py` (Fire-based) at repo root |
| Programmatic entrypoint | IDENTIFIED | `run_agent.py` - `AIAgent` class with `run_conversation()` |
| Provider configuration | IDENTIFIED | Provider plugin system at `plugins/model-providers/` |
| NVIDIA NIM support | IDENTIFIED | `plugins/model-providers/nvidia/__init__.py` - uses `NVIDIA_API_KEY` |
| Custom OpenAI-compatible | IDENTIFIED | `plugins/model-providers/custom/__init__.py` - generic endpoint |
| Skill discovery | IDENTIFIED | `skills/` dir, `agent/skill_commands.py`, `agent/skill_bundles.py` |
| Memory storage | IDENTIFIED | `agent/memory_manager.py`, files in `~/.hermes/memory/` |
| Tool registration | IDENTIFIED | `tools/registry.py` and `tools/skill_manager_tool.py` |
| V7 skill loading | GAP | V7 skills use different format (SKILL.md + tools/) than Hermes expects |
| Hermes not installed | GAP | Cannot import Hermes without `pip install -e .` |

## OpenMontage Gaps

| Requirement | Status | Evidence |
|------------|--------|----------|
| Pipeline defs | IDENTIFIED | `pipeline_defs/*.yaml` - 14 pipeline manifests |
| Pipeline loader | IDENTIFIED | `lib/pipeline_loader.py` - `load_pipeline()`, `list_pipelines()` |
| Schema validation | IDENTIFIED | `schemas/` dir with JSON schemas for artifacts |
| Tool registry | IDENTIFIED | `tools/tool_registry.py` |
| Backlot/checkpoints | IDENTIFIED | `backlot/` server + `lib/checkpoint.py` |
| Render mechanism | IDENTIFIED | Tools-based: `video_compose`, `remotion_caption_burn`, `hyperframes_compose` |
| render_demo.py purpose | IDENTIFIED | **NOT general render** - Remotion JSON-prop demo only |
| Single render command | DOES NOT EXIST | OpenMontage is agent-driven; no `python render.py` exists |
| Project creation | IDENTIFIED | Projects live in `projects/<id>/` with checkpoints in `projects/<id>/pipeline/` |

## Critical Gaps Resolved

1. **Hermes invocation**: Use `run_agent.AIAgent` with `provider='nvidia'` or `provider='custom'`
2. **Hermes installation**: Not possible without repo clone + `pip install -e .` - adapter will use subprocess with `python3 cli.py` or direct module import after `PYTHONPATH` setup
3. **V7 skill loading**: V7 skills have SKILL.md files - compatible with Hermes skill format. Copy to `~/.hermes/skills/football-emotion/` or use `--skills-dir` arg
4. **OpenMontage render**: Use `tools.video.video_compose` or `tools.video.hyperframes_compose` directly, OR run `render_demo.py` for Remotion demos only
5. **Artifact validation**: Use `lib.checkpoint.validate_checkpoint()` and `schemas.artifacts.validate_artifact()`
6. **Pipeline execution**: Must convert Hermes artifacts to OpenMontage schema artifacts, then create OpenMontage project with checkpoints

## Architecture Decision

- Hermes will be invoked as a **subprocess** (`python3 -m hermes_cli ...` or `python3 cli.py ...`) since we cannot `pip install -e .` the full Hermes-Agent
- OpenMontage render will use the **tools-based approach**: call `tools.video.video_compose.py` or `tools.video.hyperframes_compose.py` directly
- Skill loading: Copy V7 skills to a path Hermes can discover
- Memory: Write to `state/hermes_memory/` (Hermes-compatible MEMORY.md, USER.md, learned_patterns.jsonl)
