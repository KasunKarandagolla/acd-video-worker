# OpenMontage Execution Report

Run: run_20260710_180722

## OpenMontage Status

- Available: True

## Pipeline Selection

- Selected: clip-factory
- Reason: Pipeline 'clip-factory' selected for most recent argentina world cup match in 2026 workflow. Description: Multi-clip extraction pipeline. Takes long-form content (webinar, stream, presentation, interview) and produces multiple short clips optimized for social distribution. Outputs N independent deliverabl
- Candidates: ['animated-explainer', 'animation', 'avatar-spokesperson', 'character-animation', 'cinematic', 'clip-factory', 'documentary-montage', 'framework-smoke', 'hybrid', 'localization-dub', 'podcast-repurpose', 'screen-demo', 'talking-head']
- Manifest name: clip-factory
- Manifest version: 2.0

## Pipeline Load

- Loaded: True
- Stages (7): ['idea', 'script', 'scene_plan', 'assets', 'edit', 'compose', 'publish']
- Required tools: ['frame_sampler', 'subtitle_gen', 'video_compose', 'color_grade', 'audio_enhance', 'scene_detect', 'transcriber', 'video_trimmer', 'audio_mixer']

## Registry Discovery

- Ran: True
- Registered tools (95):
  - audio_energy
  - audio_probe
  - composition_validator
  - dashscope_asr
  - face_tracker
  - frame_sampler
  - scene_detect
  - transcriber
  - transcript_fetcher
  - video_analyzer
  - video_downloader
  - video_understand
  - visual_qa
  - audio_enhance
  - audio_mixer
  - dashscope_tts
  - doubao_tts
  - elevenlabs_tts
  - freesound_music
  - google_music
  - google_tts
  - music_gen
  - music_library
  - openai_tts
  - piper_tts
  - pixabay_music
  - suno_music
  - tts_selector
  - lip_sync
  - talking_head
  - cap_recorder
  - screen_capture_selector
  - screen_recorder
  - action_timeline_compiler
  - character_animation_reviewer
  - character_rig_renderer
  - character_spec_generator
  - pose_library_builder
  - svg_rig_builder
  - bg_remove
  - color_grade
  - eye_enhance
  - face_enhance
  - face_restore
  - upscale
  - code_snippet
  - comfyui_image
  - dashscope_image
  - diagram_gen
  - flux_image
  - google_imagen
  - grok_image
  - image_gen
  - image_selector
  - local_diffusion
  - math_animate
  - openai_image
  - pexels_image
  - pixabay_image
  - recraft_image
  - export_bundle
  - subtitle_gen
  - auto_reframe
  - clip_search
  - cogvideo_video
  - comfyui_video
  - corpus_builder
  - direct_clip_search
  - gemini_omni_video
  - green_screen_composite
  - green_screen_processor
  - grok_video
  - heygen_video
  - higgsfield_video
  - hunyuan_video
  - hyperframes_compose
  - kling_video
  - ltx_video_local
  - ltx_video_modal
  - minimax_video
  - pexels_video
  - pixabay_video
  - remotion_caption_burn
  - runway_video
  - seedance_replicate
  - seedance_video
  - showcase_card
  - silence_cutter
  - sora_video
  - veo_video
  - video_compose
  - video_selector
  - video_stitch
  - video_trimmer
  - wan_video
- Selected compose tool: frame_sampler

## Checkpoints

- Project initialized: True
- Checkpoints written: []

## Composition

- Attempted: True
- Tool used: frame_sampler
- Success: False
- Error: video_compose.execute() raised: 'input_path'

## FFprobe Validation

- Valid: True
- Duration: 5.0s
- Resolution: 640x480
- Codec: h264
- Size: 44030 bytes

## Success Flags

- openmontage_success: False
- pipeline_success: False
- final_success: False
