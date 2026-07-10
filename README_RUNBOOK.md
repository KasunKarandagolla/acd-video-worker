# ACD Video Worker - Runbook

## Local Repo Preparation

```bash
# Navigate to repo
cd acd-video-worker

# Ensure skill ZIP is in place
ls packages/football_emotion_skill_system_v7_final_runtime.zip

# Set up environment
cp .env.example .env
# Edit .env with your credentials
```

## Skill ZIP Placement

Place the finalized skill ZIP at:

```
packages/football_emotion_skill_system_v7_final_runtime.zip
```

The bootstrap `install_skills.sh` will extract this into `skills/football-emotion/`.

## GitHub Private Repo Push

```bash
git init
git add .
git commit -m "Initial worker setup"
git remote add origin <your_private_repo_url>
git push -u origin main
```

The `PRIVATE_REPO_URL` environment variable must point to this same repo.

## Kaggle Secrets

Set these in your Kaggle notebook (Add-ons > Secrets):

| Secret | Required | Description |
|--------|----------|-------------|
| `GITHUB_TOKEN` | Yes | GitHub PAT with repo scope |
| `PRIVATE_REPO_URL` | Yes | URL to your private acd-video-worker repo |
| `LLM_API_KEY` | Yes | OpenAI-compatible API key |
| `LLM_BASE_URL` | Yes | LLM API base URL |
| `LLM_MODEL` | Yes | Model name (e.g. gpt-4o) |
| `DISCORD_WEBHOOK_URL` | Yes | Discord webhook for status |
| `YOUTUBE_COOKIES_FILE` | No | YouTube cookies (base64) |
| `YT_DLP_COOKIES_PATH` | No | Path to cookies file |

## How to Run Worker

### On Kaggle

1. Create a new Kaggle notebook
2. Add secrets above
3. Run `kaggle/run_worker.ipynb` - it clones the repo and calls `bootstrap/bootstrap_kaggle.sh`

### Locally (for testing)

```bash
# Install dependencies
pip3 install requests pyyaml yt-dlp

# Check environment
bash bootstrap/check_environment.sh

# Clone external repos
bash bootstrap/clone_repos.sh

# Install skills
bash bootstrap/install_skills.sh

# Run a specific job
python3 scripts/run_title_theme_job.py jobs/argentina_hardest_victory.yaml
```

## How Discord Status Works

The worker posts status updates at each pipeline stage:

- `discord_notify.py` reads `DISCORD_WEBHOOK_URL` from environment
- Stages: setup, skills, LLM check, source discovery, download, render, memory, completion
- If `DISCORD_WEBHOOK_URL` is not set, notifications are silently skipped

## How Memory Sync Works

- `memory_sync.py hydrate` ensures `state/hermes_memory/` exists with MEMORY.md, USER.md, learned_patterns.jsonl
- `memory_sync.py collect --run-id <id>` captures run lessons into learned_patterns.jsonl
- `memory_sync.py push --run-id <id>` commits memory back to GitHub using GITHUB_TOKEN
- Memory survives Kaggle sessions by syncing to GitHub after each run

## How to Inspect Blockers

All run artifacts are in:

```
state/runs/<run_id>/
├── source_candidates.json
├── source_discovery_report.md
├── downloaded_assets.json
├── download_report.md
├── render_report.md
├── openmontage_render_plan.json
├── memory_update_report.md
└── session_summary.md
```

Check these reports for blocker details at each stage.

## Where Final Video/Report Appears

- Final render: `outputs/<run_id>/final_attempt.mp4` (OpenMontage render)
- Fallback render: `outputs/<run_id>/fallback_render_attempt.mp4` (ffmpeg fallback)
- Session summary: `state/runs/<run_id>/session_summary.md`
- Memory: `state/hermes_memory/` (synced to GitHub)

## Architecture Notes

- This repo is the **control/worker** repo - it does NOT vendor Hermes-Agent or OpenMontage
- Hermes-Agent and OpenMontage are **cloned at runtime** into `external/`
- The `external/` directory is gitignored and never committed
- Kaggle is a **disposable execution machine**
- GitHub is the **persistent source of truth and memory store**
- The default job is title/theme only - no sample footage required
