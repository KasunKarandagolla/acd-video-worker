# Setup Validation Report

**Passed:** 24 | **Failed:** 0 | **Blocked:** 2

| Check | Status | Details |
|-------|--------|---------|
| hermes_commit | PASSED | Hermes at pinned commit 5ecc0798 |
| openmontage_commit | PASSED | OpenMontage at pinned commit f633b5f4 |
| hermes_install | PASSED | Hermes CLI: Hermes Agent v0.18.2 (2026.7.7.2) · upstream 4281151a · local 5ecc0798 (+1 carried commit)
Install directory: /home/kasun/Music/Director/acd-video-worker/external/Hermes-Agent
Install method: git
Python: 3.11.0rc1
OpenAI SDK: 2.24.0 |
| hermes_profile | PASSED | Profile exists with all required dirs |
| skill_discovery | PASSED | All 24 skills discovered |
| skill_validation | PASSED | Result: PASSED |
| memory_write_read | PASSED | MEMORY: 0/2200, USER: 0/1375 (writable) |
| session_search | PASSED | All session tables present: ['schema_version', 'sessions', 'messages', 'sqlite_sequence', 'state_meta', 'gateway_routing', 'compression_locks', 'messages_fts', 'messages_fts_data', 'messages_fts_idx', 'messages_fts_content', 'messages_fts_docsize', 'messages_fts_config', 'messages_fts_trigram', 'messages_fts_trigram_data', 'messages_fts_trigram_idx', 'messages_fts_trigram_content', 'messages_fts_trigram_docsize', 'messages_fts_trigram_config'] |
| hindsight | BLOCKED | No Hindsight config (built-in memory only) |
| openmontage_import | PASSED | OpenMontage imports cleanly |
| tool_registry | PASSED | Tool registry OK, runtimes: {'ffmpeg': True, 'remotion': False, 'hyperframes': True} |
| pipeline_load | PASSED | Pipeline: documentary-montage
Stages: ['idea', 'scene_plan', 'assets', 'edit', 'compose'] |
| ffmpeg_provider | PASSED | Available: [] |
| schema_lock | PASSED | Schema lock mappings complete + validation OK |
| browser_capability | PASSED | Browser verdict: BROWSER_SUPPORTED |
| acd_worker_dry_run | PASSED | ACD worker dry-run successful |
| runtime_folders | PASSED | All runtime folders writable |
| youtube_discovery | PASSED | yt-dlp search works: 3 results |
| candidate_ranking | PASSED | 7-axis rubric works: scores 5.5, 3.1 |
| sequential_acquisition | PASSED | Acquisition engine initializes correctly |
| failure_replacement | PASSED | Failure classification + replacement logic works |
| media_validation | PASSED | ffprobe + ffmpeg available for validation |
| checkpoint_resume | PASSED | Checkpoint save/load works |
| source_media_review_schema | PASSED | source_media_review structure matches schema |
| asset_manifest_schema | PASSED | asset_manifest structure matches OpenMontage schema |
| hindsight_persistence | BLOCKED | Hindsight blocked on Kaggle (no daemon, no free persistent deployment); built-in memory + session search + project records work |
