# Shared Contracts — Pipeline Artifacts

Version: 1.0. These are the canonical schemas every skill in this package reads from and writes
to. Skills should not invent parallel/incompatible shapes for the same concept — if a skill needs
a field this file doesn't have, add it here (and note the addition in that skill's SKILL.md)
rather than defining a local variant.

All schemas that carry a factual claim include a verification/confidence field per
`shared/references/verification-standard.md`. All schemas that carry a music/SFX asset include a
license-verification field per `football-rights-safe-audio-license-checker`.

---

## user_instruction_profile

Produced by: `football-story-strategy` (parsing stage). Consumed by: almost everything downstream.

```yaml
user_instruction_profile:
  raw_instruction: string
  topic: string
  players: [string]
  teams: [string]
  competitions: [string]
  target_emotion: comeback | heartbreak | revenge | legacy | pressure | underdog | last_chance | iconic_skill | rivalry | national_pride | heroic_failure | humiliation
  story_type: string          # matches a story structure name in emotion-pattern-library.md
  output_duration_target: string
  style_preference: cinematic | documentary | motivational | analysis | unknown
  verification_requirements: strict | normal
```

---

## source_video_candidate

Produced by: `football-source-discovery`. Consumed by: `football-visual-scene-analysis`.

```yaml
source_video_candidate:
  candidate_id: string
  title: string
  url: string | null
  channel: string | null
  source_type: official | broadcaster | fan_edit | documentary | news | analysis | shorts | unknown
  approximate_duration: string | null
  main_player_team_match: string
  emotion_types: [string]
  story_role: hook_reference | source_clip | deep_analysis_reference | audio_reference | thumbnail_reference
  discovery_score_10: float
  visual_review_status: verified | unverified | unavailable
  audio_review_status: verified | unverified | unavailable
  metadata_confidence: high | medium | low
  deep_analysis_candidate: yes | no | maybe
  reason_for_selection: string
  reason_for_rejection: string | null
  rights_reused_content_risk: low | medium | high | unknown
  verification_status: verified | unverified | requires_manual_review
```

---

## video_scene_analysis / scene_candidate

Produced by: `football-visual-scene-analysis`. Consumed by: `football-timestamp-extraction`.

```yaml
video_scene_analysis:
  video_id: string
  title: string
  url: string | null
  story_angle: string
  emotional_reason_it_works: string
  verification_status: verified | partial | unverified
  scenes:
    - scene_id: string
      source_timestamp_start: string | null
      source_timestamp_end: string | null
      editor_timeline_role: hook | setup | buildup | pressure | reversal | climax | aftermath | outro
      scene_type: string        # see timestamp-extraction skill's scene taxonomy
      visual_description: string
      audio_description: string
      editing_technique_observed: string
      emotional_purpose: string
      reusable_lesson: string
      confidence: high | medium | low | unusable
      manual_review_needed: boolean
```

---

## clip_candidate / clip_scorecard

Produced by: `football-timestamp-extraction` (candidate) then scored by `football-clip-scoring`.

```yaml
clip_candidate:
  clip_id: string
  source_video_id: string
  source_range: string          # "00:04:12-00:04:29"
  topic_match: string
  scene_type: string
  emotional_role: hook | context | pressure | reversal | climax | aftermath | support | reject
  visual_signs: [string]
  audio_signs: [string]
  story_relevance: string
  rights_risk: low | medium | high | unknown
  verification_status: verified | partial | unverified
  scorecard:
    emotional_strength_2: float      # 0-2
    visual_clarity_2: float          # 0-2
    story_relevance_2: float         # 0-2
    audio_commentary_value_1: float  # 0-1
    uniqueness_1: float              # 0-1
    editability_1: float             # 0-1
    rights_reused_content_risk_1: float  # 0-1
    total_10: float
  recommended_use: hook | context | buildup | climax | aftermath | reject
  openmontage_notes: string
```
Decision thresholds: `8–10` core story clip · `6–7.9` supporting clip · `4–5.9` context-only/replace · `<4` reject.

---

## story_plan

Produced by: `football-story-strategy`. Consumed by: `football-narration-scriptwriting`, `openmontage-edit-planning`.

```yaml
story_plan:
  project_title: string
  story_structure: string        # name from emotion-pattern-library.md
  hook_pattern: string
  target_duration: string
  sections:
    - section_id: string
      timeline_range: string
      emotional_role: hook | context | pressure | reversal | climax | aftermath
      required_clip_types: [string]
      narrative_purpose: string
  minimum_clip_package: [string]  # e.g. for heartbreak: hope/setup, final chance, decisive failure, reaction, crowd/team, aftermath
```

---

## caption_plan / thumbnail_candidate

Produced by: `football-caption-thumbnail-direction`.

```yaml
caption_plan:
  section_id: string
  caption_text: string | null
  caption_type: emotional | commentary | quote
  placement_notes: string
  timing_notes: string

thumbnail_candidate:
  frame_source_clip_id: string
  frame_timestamp: string | null
  thumbnail_score_10:
    face_emotion: float        # 0-2
    story_clarity: float       # 0-2
    contrast_readability: float # 0-2
    curiosity: float           # 0-2
    low_clutter: float         # 0-1
    non_misleading: float      # 0-1
  text_options: [string]        # 2-4 words each
  verification_status: verified | unverified
```

---

## music_sfx_candidate

Produced by: `football-music-library-selector`. Consumed by: `football-rights-safe-audio-license-checker`, `football-audio-music-director`.

```yaml
music_sfx_candidate:
  asset_id: string
  asset_type: music | sfx | crowd | silence_strategy
  title: string
  creator: string | null
  source_platform: string        # Pixabay, YouTube Audio Library, Incompetech, Freesound, etc.
  category: sad_piano | cinematic_rise | epic_orchestral | dark_ambient | heartbeat_tension | motivational | documentary_piano | crowd_ambience | whoosh | impact_bass | riser | camera_shutter | silence_cut | commentator_echo | other
  duration: string | null
  license_code: PD | CC0 | CC-BY | Pixabay | Mixkit | YAL | FMA | FS-CC | unknown
  is_exact_asset_page: boolean   # false if this is a search/category link, not a direct asset page
  source_link: string
  football_use_note: string
  suitability_score_10: float
  risk_flag: none | requires_verification | high_risk
  license_verification_required: true   # always true at this stage — see license checker
```

---

## license_verification_record

Produced by: `football-rights-safe-audio-license-checker`. Gates use of any `music_sfx_candidate`.

```yaml
license_verification_record:
  asset_id: string
  exact_asset_url: string
  license_type: string
  creator: string
  attribution_required: boolean
  attribution_text: string | null
  checked_date: string
  content_id_risk: low | medium | high | unknown   # DISTINCT from license_type — a correctly licensed track can still be claim-risky
  status: approved | rejected | needs_more_info
  rejection_reason: string | null
```

---

## commentary_rights_check

Produced by: `football-rights-safe-audio-license-checker`. Gates direct use of match/broadcast commentary audio. This is separate from music/SFX licensing.

```yaml
commentary_rights_check:
  commentary_source: string
  language: string
  broadcaster: string
  match_rightsholder: string
  is_official_clip: true | false | unknown
  is_reupload: true | false | unknown
  transcript_used_only: true | false
  direct_audio_used: true | false
  risk_level: low | medium | high | unknown
  recommendation: use_transcript_only | short_quote_with_risk | user_must_supply_rights | avoid | needs_legal_review
  checked_date: string
  provenance: verified_from_source | user_supplied | estimated_by_editor | creative_hypothesis
```

---

## audio_plan (section-by-section)

Produced by: `football-audio-music-director`, refined by `football-commentary-ducking-mixer`.

```yaml
audio_plan_segment:
  section_id: string
  dominant_audio: commentary | narrator | crowd | music | silence | sfx
  music_asset_id: string | null       # must reference an approved license_verification_record
  commentary_asset_id: string | null  # direct commentary audio, if used
  commentary_rights_check_required: boolean
  commentary_rights_check_id: string | null  # required when direct commentary audio is used
  music_action: start | rise | duck | drop | remove | continue
  ducking_required: boolean
  silence_beats: [string]
  sfx_events: [string]
  volume_notes: string
  reason: string
  license_verification_required: true
  provenance: verified_from_source | measured_by_tool | user_supplied | estimated_by_editor | creative_hypothesis
```

---

## openmontage_edit_plan (edit_decisions-shaped)

Produced by: `openmontage-edit-planning`. This name/shape intentionally mirrors OpenMontage's own
canonical `edit_decisions` artifact (see `implementation/IMPLEMENTATION_PLAN_HERMES_OPENMONTAGE.md`
for the confirmed vs. assumed parts of that mapping).

```yaml
openmontage_edit_plan:
  project_title: string
  target_duration: string
  story_structure: string
  render_runtime: hyperframes | remotion | ffmpeg   # per OpenMontage governance, must be user-confirmed, not silently defaulted
  sections:
    - section_id: string
      timeline_range: string
      emotional_role: hook | context | pressure | reversal | climax | aftermath
      clips: [clip_id]
      cut_style: hold | fast_cut | beat_cut | reaction_cut
      transition_in: hard_cut | fade | cross_dissolve | match_cut | none
      transition_out: hard_cut | fade | silence_cut | none
      speed: normal | slow_motion | speed_ramp
      effect: none | subtle_zoom | impact_zoom | black_white | freeze_frame
      caption: string | null
      audio_priority: commentary | music | silence | crowd
      music_action: start | rise | duck | drop | remove | none
      sfx: [string]
      reason: string
  quality_checks: [string]
```

---

## openmontage_audio_operations

Produced by: `openmontage-audio-operation-mapper`. Converts `audio_plan` into OpenMontage-track-shaped operations.

```yaml
audio_plan_version: "1.0"
video_duration_seconds: number
tracks:
  - track_id: string
    track_type: music | commentary | sfx | crowd
    clips:
      - start_time: number
        end_time: number
        asset_id: string | null
        source: string | null
        fade_in: number
        fade_out: number
        volume_db: number
        ducking: {trigger: string, amount_db: number, attack_ms: number, release_ms: number} | null
silence_cuts:
  - start_time: number
    end_time: number
    reason: string
master:
  target_lufs: -14.0
  true_peak_db: -1.0
  loudness_range_lu: number
  measurement_required: true
  audio_loudness_measurement_id: string | null  # must point to measured artifact before final pass
  measured_lufs: number | null       # copied from audio_loudness_measurement only after measured_by_tool
  measured_true_peak_db: number | null
  measurement_status: not_rendered | measured_by_tool | failed | not_applicable
```

---

## qc_report

Produced by: `football-retention-quality-control`, `football-audio-quality-control`.

```yaml
qc_report:
  qc_type: retention | audio | reused_content
  pass: boolean
  findings:
    - finding: string
      severity: low | medium | high | blocking
      section_id: string | null
      required_fix: string
  transformation_notes: string | null   # for reused-content risk specifically
  overall_risk_level: low | medium | high | unknown
```

---

## hermes_memory_update

Produced by: `hermes-football-memory-learning`. Distilled to fit Hermes' MEMORY.md/USER.md budget
(~2,200 / ~1,375 characters respectively) — see that skill's SKILL.md for the size discipline.

```yaml
hermes_memory_update:
  project_id: string
  topic: string
  story_type: string
  short_lessons: [string]        # each a single sentence, MEMORY.md-scale
  best_source_types: [string]
  successful_hook_pattern: string | null
  successful_audio_pattern: string | null
  clips_to_avoid_next_time: [string]
  full_project_record_path: string   # path to the large on-disk record — NOT written into MEMORY.md itself
```

---

# V3 Editorial Journey Additions

These schemas were added after integrating the professional editorial workflow references. They prevent the agent from jumping directly from clips to timeline assembly.

## v3 editorial_journey_state

Produced by: `social-edit-reasoning`. Consumed by: all stage-specific skills.

```yaml
editorial_journey_state:
  current_stage: 1-12
  stage_name: brief_intake | sourcing | verification | timestamping | curation | sequencing_pacing | audio_music | visual_cohesion | graphics_text | assembly | qa | memory
  locked_decisions:
    emotional_question: string | null
    tonal_flavor: string | null
    runtime_target: string | null
    platform: string | null
    arc_phases_in_scope: [string]
    music_locked: boolean
    target_aspect_ratio: string | null
  missing_prerequisites: [string]
  recommended_next_skill: string
  required_reference: string
  reason: string
```

## v3 brief_interpretation

Produced by: `football-story-strategy` / `social-edit-reasoning`. Must exist before sourcing.

```yaml
brief_interpretation:
  raw_request: string
  emotional_question: string
  tonal_flavor: triumphant | bittersweet | defiant | introspective | angry | tragic | heroic | unknown
  runtime_target: 15s | 30s | 60s | 3min_plus | 8_12min_longform | custom
  platform: youtube_longform | youtube_shorts | tiktok | instagram_reels | mixed | unknown
  arc_phases_in_scope: [cold_open, setup, fall, grind, turning_point, triumph_or_payoff, coda]
  clip_budget_target: string
  non_negotiable_moments: [string]
  downstream_locks:
    narrative_structure: string
    sourcing_scope: string
    music_scope: string
    graphics_intensity: minimal | moderate | sophisticated
    visual_cohesion_hint: archive | stylized | seamless | undecided
```

## v3 visual_cohesion_plan

Produced by: `openmontage-edit-planning` or the visual stage. Consumed by QA.

```yaml
visual_cohesion_plan:
  treatment_tier: documentary_archive | stylized_color_coded | transparent_seamless
  target_aspect_ratio: string
  aspect_ratio_strategy: crop_to_single_format | intentional_mismatch | pillarbox_letterbox | mixed
  color_strategy: none | per_phase_grade | global_lut | manual_match
  mismatch_risks:
    - clip_id: string
      issue: aspect_ratio | resolution | color_temperature | exposure | compression | framerate
      action: accept_as_story | correct | replace | bridge_with_graphics
  reason: string
```

## v3 graphics_text_plan

Produced by: `football-caption-thumbnail-direction`. Consumed by edit planning and QA.

```yaml
graphics_text_plan:
  text_principle: minimum_effective_dose
  cards:
    - card_id: string
      function: clarification | emphasis | metadata
      section_id: string
      text: string
      placement: lower_third | center | corner_safe | overlay | static_background
      duration_seconds: number
      safe_zone_checked: boolean
      phone_readability_checked: boolean
      sync_to_audio: none | appears_before_phrase | holds_through_phrase | exits_after_phrase
  rejected_text:
    - text: string
      reason: overexplains | redundant | unreadable | competes_with_action | metadata_overuse
```

## v3 assembly_plan

Produced by: `openmontage-edit-planning`. Consumed by QA and OpenMontage adapter.

```yaml
assembly_plan:
  assembly_workflow: build_to_music | build_cuts_first
  music_structure_markers:
    intro_end: string | null
    build_peak: string | null
    breakdown_start: string | null
    final_drop_or_outro: string | null
  phase_runtime_allocation:
    - section_id: string
      target_percent: number
      actual_percent: number
      status: ok | too_long | too_short | needs_recut
  critical_sync_cuts:
    - cut_id: string
      section_id: string
      sync_target: kick | drop | vocal_entry | silence_cut | commentary_line | crowd_roar
      exact_timing_required: boolean
  track_layout:
    video_tracks: [string]
    audio_tracks: [music, commentary_or_vo, crowd, sfx]
  handles_seconds: 2-5
```

## v3 full_qa_report

Produced by: `football-retention-quality-control`. Stronger than basic `qc_report`; it separates fix vs re-cut.

```yaml
full_qa_report:
  pass: boolean
  technical_qa:
    pass: boolean
    findings: [string]
  editorial_qa:
    pass: boolean
    findings: [string]
  platform_qa:
    pass: boolean
    findings: [string]
  reused_content_gate:
    pass: boolean
    findings: [string]
  vibe_check:
    pass: boolean
    note: string
  required_loopbacks:
    - target_stage: brief_intake | sourcing | curation | sequencing | audio | visual_cohesion | graphics | assembly | license | qa
      target_skill: string
      reason: string
      severity: low | medium | high | blocking
```

# V5 Patch Artifact Extensions

These artifacts are additive. They do not replace the v4 contracts; they gate whether v4 artifacts may become final.

```yaml
match_fact_lock:
  status: verified | ambiguous | not_found | user_confirmation_required
  competition: string
  match: string
  date: string
  teams: [string, string]
  score: string
  key_events: []
  factual_uncertainties: []
  must_not_claim: []

fact_provenance_report:
  pass: boolean
  checked_artifacts: []
  findings: []

repo_setup_status:
  hermes_path: string
  hermes_exists: boolean
  openmontage_path: string
  openmontage_exists: boolean
  pinned_commit_files_present: boolean
  preflight_possible: boolean
  missing_items: []
  exact_commands_to_fix: []
  allowed_next_action: stop | simulate_only | proceed

openmontage_schema_lock:
  schemas_path: string
  schemas_found: []
  schema_version_or_commit: string
  mapped_fields: []
  unmapped_fields: []
  forbidden_assumptions: []
  bridge_status: passed | degraded | blocked

arc_revision_gate:
  original_emotional_question: string
  verified_footage_supports_original: true | false | partial
  strongest_verified_story_found: string
  recommended_arc: string
  change_required: boolean
  reason: string

footage_rights_risk_record:
  source_type: official | broadcaster | fan_upload | commentary_channel | social_clip | user_supplied
  recommendation: usable_with_risk | avoid | user_must_supply_rights | needs_legal_review

audio_loudness_measurement:
  measured_by: ffmpeg_loudnorm | other
  integrated_lufs: number
  true_peak_db: number
  loudness_range_lra: number
  pass: boolean
  correction_needed: boolean
  suggested_filter: string

speech_ducking_regions:
  method: vad | transcript | manual_marker | user_supplied
  regions: []
  verification_status: verified | estimated | manual_review_needed

emotion_evidence:
  visual_body_language: []
  audio_evidence: []
  context_evidence: []
  emotion_claim_confidence: low | medium | high

broadcast_overlay_map:
  scorebug_present: boolean
  location: top_left | top_right | bottom_left | bottom_right | unknown
  scoreboard_text: string
  obstructs_action: boolean
  crop_safe: boolean
  caption_safe_zones: string

video_color_metadata:
  hdr_detected: true | false | unknown
  transfer_function: sdr | hlg | pq | unknown
  tone_map_required: true | false | unknown
  tone_map_method: string
  post_tonemap_review_required: boolean

export_profile:
  platform: youtube_longform | youtube_shorts | tiktok | instagram_reels | other
  aspect_ratio: string
  resolution: string
  codec: string
  container: string
  audio_codec: string
  target_lufs: number
  true_peak: number
  hdr_metadata_policy: preserve | tonemap_to_sdr | strip | unknown
  pass: boolean

memory_entry:
  lesson: string
  evidence_type: measured_result | editor_observation | user_preference | failed_attempt | hypothesis
  confidence: low | medium | high
  do_not_generalize_beyond: string
  source_project: string
```
