# V4 Repo Bridge Addendum — read before routing to execution

When the task is only conceptual planning, use the editorial routing below. When the task will be executed inside the confirmed Hermes + OpenMontage setup, first consult:

1. `shared/references/repo-bridge/repo-source-lock.md`
2. `shared/references/repo-bridge/openmontage-agent-contract.md`
3. `shared/references/repo-bridge/openmontage-tool-registry-preflight.md`
4. `shared/references/repo-bridge/openmontage-stage-skill-map.md`

Execution must go through OpenMontage pipeline manifests, stage director skills, tool registry discovery, canonical artifacts, checkpoints, and project workspace paths. Do not turn the editorial route into a parallel video engine.

---

# Pipeline Routing Guide — Football Emotion Skill System v3

This is a lightweight routing guide, not a competing orchestrator. Hermes remains the agent orchestration layer and OpenMontage remains the edit/render execution layer. This file prevents the LLM from losing any stage of the editorial journey.

## Non-negotiable editorial journey

The default route for a real project is now stage-based:

| Stage | What gets locked | Primary skill(s) |
|---|---|---|
| 1. Brief interpretation | emotional question, tone, runtime, platform, arc scope | `social-edit-reasoning` + `football-story-strategy` |
| 2. Sourcing strategy | search targets, source diversity, candidate quantity | `social-edit-reasoning` + `football-source-discovery` |
| 3. Visual/source verification | what is actually visible/audible | `football-visual-scene-analysis` |
| 4. Timestamp extraction | usable scene ranges and scene roles | `football-timestamp-extraction` |
| 5. Clip curation/scoring | selected clips per arc phase | `football-clip-scoring` |
| 6. Sequencing/pacing | phase order, shot durations, rhythm | `football-story-strategy` + `football-pro-cutting-pacing` |
| 7. Music/audio strategy | approved candidates, dominance, silence/ducking/SFX | `football-music-library-selector` → `football-rights-safe-audio-license-checker` → `football-audio-music-director` |
| 8. Visual cohesion | archive/stylized/seamless treatment, aspect ratio, grade | `social-edit-reasoning` + `openmontage-edit-planning` |
| 9. Graphics/text | title cards, quotes, safe zones, typography | `football-caption-thumbnail-direction` |
| 10. Assembly | build-to-music timeline, layers, transitions, handles | `openmontage-edit-planning` + `openmontage-audio-operation-mapper` |
| 11. QA and final gate | technical QA, editorial QA, platform QA, reused-content gate | `football-audio-quality-control` + `football-retention-quality-control` |
| 12. Memory | compact lessons after project | `hermes-football-memory-learning` |

## Stage dependency rule

Do not skip or reverse stages without writing a reason. The most common failure is jumping from source clips directly to an edit plan. A professional edit needs brief → sourcing → curation → sequencing → music → cohesion → graphics → assembly → QA.

## Default route for a new football-emotion video

1. `social-edit-reasoning` — determine current stage and lock brief requirements.
2. `football-story-strategy` — produce `brief_interpretation` and `story_plan`.
3. `football-source-discovery` — search according to brief and source discipline.
4. `football-visual-scene-analysis` — verify real frames/audio, do not fake details.
5. `football-timestamp-extraction` — create scene candidates.
6. `football-clip-scoring` — select clips with phase coverage and risk flags.
7. `football-pro-cutting-pacing` — build pacing and cut rhythm decisions.
8. `football-music-library-selector` — propose candidate music/SFX only.
9. `football-rights-safe-audio-license-checker` — mandatory license approval gate.
10. `football-audio-music-director` — choose audio dominance and music/silence strategy.
11. `football-commentary-ducking-mixer` — preserve commentary/VO audibility.
12. `openmontage-audio-operation-mapper` — turn audio plan into OpenMontage-shaped operations.
13. `football-caption-thumbnail-direction` — plan text, quote, typography, and thumbnail frame logic.
14. `openmontage-edit-planning` — assemble timeline with visual cohesion and build-to-music workflow.
15. `football-audio-quality-control` — focused audio and sync QC.
16. `football-retention-quality-control` — full technical/editorial/platform/reused-content gate.
17. `hermes-football-memory-learning` — store reusable learnings.

## Loop-back rules from QA

- Weak emotional arc → return to `football-story-strategy` / sequencing.
- Weak source evidence → return to `football-source-discovery`.
- Redundant or filler clips → return to `football-clip-scoring`.
- Off-beat climax or wrong build → return to `football-pro-cutting-pacing` or audio director.
- Visual mismatch looks accidental → return to visual cohesion planning in `openmontage-edit-planning`.
- Text unreadable or excessive → return to `football-caption-thumbnail-direction`.
- Speech buried or music unsafe → return to audio/license skills.
- Reused-content risk high → return to clip selection, narration, structure, and source diversity.

## Fast routes

### User only asks for music
`football-music-library-selector` → `football-rights-safe-audio-license-checker` → `football-audio-music-director`. Use `social-edit-reasoning` first if runtime/tone/platform are unclear.

### User asks to score clips
`social-edit-reasoning` to confirm Stage 3/5 → `football-visual-scene-analysis` if clips are unverified → `football-clip-scoring`.

### User already has a story plan and clips
Start at Stage 6: `football-pro-cutting-pacing`, then audio, text, assembly, QA. Do not skip visual cohesion or QA.

### User asks for final audit
Run `football-audio-quality-control`, then `football-retention-quality-control`. Reused-content risk remains a blocking section inside retention QC.

## Safety gates

- No source visual/audio detail is verified unless frames/audio/transcript were actually inspected.
- No music/SFX candidate is usable until a `license_verification_record` marks it `approved`.
- No final export passes if the edit is only a highlight compilation, has weak transformation, masks speech, ignores visual mismatch, or fails target-platform readability.

## V5 safety routing patch

0. If request is current/latest/ambiguous, run `football-match-identification` before brief interpretation.
1. If local repos are needed, run `repo_setup_status` and stop if setup is missing unless user asked for simulation only.
2. Run OpenMontage preflight and schema lock before producing real OpenMontage operations.
3. Run `football-fact-provenance-gate` before final artifacts and Hermes memory.
4. After sourcing/verification, run `arc_revision_gate` and re-flow if the footage contradicts the planned arc.
5. After QA, run `football-platform-export-validator` before delivery.

---

## V7 reusable-skill boundary

The package's job is to enforce process, gates, artifact contracts, and reusable editorial heuristics. It must not become a fixed recipe for a single Argentina video or any other one-off theme.

At runtime, the LLM must still choose the story, clips, pacing, audio priority, visual treatment, and user questions based on verified footage and available OpenMontage tools.

If a simulation reveals a useful idea, accept it into the skill system only if it generalizes across many football/emotional-video projects. Otherwise keep it as a project artifact or memory lesson, not a skill rule.

Before OpenMontage execution, follow `shared/references/repo-bridge/openmontage-pipeline-manifest-preflight.md` and keep native artifacts blocked until schema lock passes.
