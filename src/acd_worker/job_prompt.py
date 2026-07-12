"""One production job prompt; creative stages remain inside Hermes/OpenMontage."""

from __future__ import annotations

from pathlib import Path


PRELOADED_SKILLS = (
    "hermes-openmontage-repo-bridge",
    "social-edit-reasoning",
    "football-story-strategy",
)


def build_job_prompt(
    *,
    run_id: str,
    project_id: str,
    request: str,
    worker_root: Path,
    openmontage_root: Path,
    project_dir: Path,
    source_manifest_path: Path,
    result_path: Path,
) -> str:
    acquisition_command = worker_root / "scripts" / "acquire_sources.py"
    return f"""You are the AI Creative Director for one production run.

RUN ID: {run_id}
PROJECT ID: {project_id}
USER REQUEST:
{request}

APPROVED PATHS:
- ACD worker root: {worker_root}
- pinned OpenMontage root: {openmontage_root}
- OpenMontage project workspace: {project_dir}
- worker-owned source manifest: {source_manifest_path}
- mandatory final result file: {result_path}

OWNERSHIP CONTRACT
1. You (Hermes) own request interpretation, creative reasoning, skill selection, reflection, creative loopbacks, memory, and high-level workflow decisions.
2. The complete installed Football Emotion Skill System is authoritative creative/editing doctrine. The preloaded bridge, social-edit-reasoning, and football-story-strategy skills are entry points, not the entire method. Discover and use every additional football skill relevant to this job, including visual/audio understanding, source discovery, timestamps, clip scoring, cutting/pacing, narration strategy, music/SFX/ducking, graphics, transitions, color, rights, retention, QA, and memory learning. Do not rewrite or reduce the skills.
3. OpenMontage owns its native pipeline, manifests, director skills, ToolRegistry, artifact schemas, runtime routing, video_compose, rendering, checkpoints/Backlot artifacts, and native review. Read AGENT_GUIDE.md, PROJECT_CONTEXT.md, the selected pipeline manifest (documentary-montage is the first candidate for football sourced footage), and each native stage director skill before acting. Use the real ToolRegistry and real native tools. Never invent a command or rebuild OpenMontage stages in the ACD worker.
4. The ACD worker owns only sources, free-only/rights policy, run state, final validation and packaging. Do not add creative workflow code to it.

SOURCE BOUNDARY
- Read the source manifest. User-provided paths/URLs are leads, not automatic rights clearance.
- You may discover and rank candidate sources creatively using supported Hermes/OpenMontage capabilities.
- For actual download/replacement, call only the worker-owned boundary below with multiple ranked candidates for one story slot; it tries them sequentially, validates media, records failures and updates the manifest:
  python3 {acquisition_command} --manifest {source_manifest_path} --output-dir {project_dir / 'source_media'} --slot <safe-slot-id> --url <candidate-1> --url <candidate-2>
- Never bypass DRM, login, cookies, CAPTCHA, geo/access controls or protected playback. Do not use proxies or stolen credentials. If lawful downloadable footage cannot be obtained, return a structured blocker.

QUALITY AND POLICY
- $0 only: no paid API, subscription, or paid asset. No local LLM/VLM requirement. A configured free cloud model/vision endpoint is permitted.
- Free cloud vision/frame analysis is allowed by the product default. On its first use, record a clear one-time disclosure in the project record/result summary; do not repeatedly interrupt later runs once durable project memory proves disclosure occurred.
- Do not rely on transcripts. Music-only/no-voice footage requires frame/vision understanding plus audio/music/emotion analysis.
- Preserve truthful fact provenance and rights-risk records. Transformative intent is not a legal-safety guarantee.
- Use FFmpeg where OpenMontage natively uses it for analysis, technical operations and validation.
- Respect native approval gates. If the request/config does not already contain the required approval, return BLOCKED with code APPROVAL_REQUIRED and the exact decision needed; never silently self-approve.
- Bound retries/reflection by the Hermes turn limit and machine resources. Never report compose/dry-run/fixture output as a render.
- After a real success or failure, apply hermes-football-memory-learning for durable lessons only; do not expose hidden reasoning.

DELIVERY CONTRACT
- A delivered claim requires a real OpenMontage-rendered media file and successful native review. The ACD worker will independently ffprobe it; your claim is only a candidate until that validation passes.
- Before ending, write exactly one UTF-8 JSON object (no markdown) to {result_path}. Create its parent directory if necessary.
- The object must follow this shape:
{{
  "schema_version": "1.0",
  "run_id": "{run_id}",
  "status": "delivered|blocked|failed",
  "output_media": [{{"path": "absolute path inside {project_dir}", "role": "primary"}}],
  "openmontage_artifacts": [{{"path": "absolute path", "kind": "render_report"}}],
  "source_requests": [],
  "blocker": null,
  "error": null,
  "summary": "short factual summary"
}}
- For blocked, output_media may be empty and blocker must be {{"code": "STABLE_CODE", "message": "actionable message", "phase": "...", "evidence": {{}}}}.
- For failed, output_media may be empty and error must use the same fields.
- Print the same raw JSON object as your final response, with no prose or markdown fences.
"""
