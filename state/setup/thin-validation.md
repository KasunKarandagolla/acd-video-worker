# Thin Runtime Validation

| Gate | Status | Evidence |
|---|---|---|
| hermes_pin | passed | 5ecc07986f46463ca3096679b03a46402eb19cee; binary smudge difference ignored |
| openmontage_pin | passed | f633b5f428b9be9a2afecba851dfddd101619756 |
| production_boundary | passed | thin controller only |
| python_compile | passed | compiled |
| focused_tests | passed | Discord notification failed: offline
----------------------------------------------------------------------
Ran 15 tests in 0.942s

OK |
| hermes_cli | blocked | Hermes CLI is not installed |
| hermes_profile | blocked | /root/.hermes/profiles/football-emotion |
| football_skills | blocked | profile skills missing: /root/.hermes/profiles/football-emotion/skills |
| canonical_skill_validation | passed | ============================================================
VALIDATION SUMMARY
============================================================
Passed checks:   230
Warnings:        0
Errors:          0

Result: PASSED |
| free_model_endpoint | blocked | Hermes profile config is missing |
| openmontage_manifest | passed | /workspace/scratch/3ca37befe28d/acd-video-worker/external/OpenMontage/pipeline_defs/documentary-montage.yaml |
| openmontage_registry | blocked | OpenMontage virtual environment is not installed |
| remotion_runtime | blocked | node+npx+remotion node_modules |
| ffmpeg_ffprobe | passed | required for render/validation |
| source_acquisition | blocked | yt-dlp Python package |
| discord | blocked | optional; run is unaffected when absent |

Passed: 8  Failed: 0  Blocked: 8
