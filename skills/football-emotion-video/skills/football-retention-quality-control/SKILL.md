---
name: football-retention-quality-control
description: Use as the final check before delivering a football emotion video plan — e.g. "run QC on this video plan", "check this for reused-content risk", "is this ready to deliver", "final review before rendering". Activates once a complete openmontage_edit_plan (with audio, captions, and thumbnail decisions) exists and needs a whole-video pass for retention/professionalism AND reused-content/copyright risk before handoff to rendering. Combines both checks because they must be evaluated against the same finished plan together, not separately.
---

# Football Retention & Quality Control

The final gate before a plan is considered delivery-ready. Runs two checks against the same
finished `openmontage_edit_plan`: a retention/professionalism pass, and a reused-content/copyright
risk pass. These are combined in one skill because approving one without the other risks shipping
a plan that's retention-strong but copyright-risky, or vice versa — see
`analysis/04_skill_architecture_decision.md` for why this merge was made.

## When to use this

- A complete `openmontage_edit_plan` exists (clips, cuts, captions, audio references, thumbnail)
- `football-audio-quality-control` has already passed (this skill assumes audio-specific issues were caught there — it re-checks audio only at the whole-plan level, e.g. "does the audio *strategy* fit the story," not dB levels again)

## Required inputs

- Complete `openmontage_edit_plan`
- `caption_plan`, `thumbnail_candidate` selections
- Source video list (for reused-content assessment)
- Passing `qc_report` (audio) from `football-audio-quality-control`

## Workflow — Part 1: Retention & Professionalism Checklist

1. Does the hook show emotion within 5-10 seconds?
2. Does every major action have a reaction?
3. Are emotional moments allowed to breathe (no premature cuts)?
4. Is the audio hierarchy respected (commentary/silence given room where they should dominate)?
5. Are effects scene-motivated, not decorative?
6. Are captions short and useful, not clutter?
7. Is the ending meaningful, not just "the last goal"?
8. Does pacing vary across the video rather than staying flat?
9. Is the thumbnail non-misleading relative to the actual content?

## Workflow — Part 2: Reused-Content / Copyright Risk Checklist

1. What percentage of runtime comes from a single dominant source? High concentration from one source raises risk — note it even if no single rule is violated.
2. Does the plan add original transformation: narration, structural reordering, analysis, pacing decisions, captions — not just re-cutting existing footage in sequence?
3. Are individual clip durations kept to what the story actually needs, rather than long unbroken segments from one source?
4. Does the plan avoid being, in substance, a re-edit of an existing compilation/fan-edit?
5. Are all referenced music/SFX assets confirmed `approved` by the license checker (cross-check against `license_verification_record`s — a `blocking` finding if any referenced asset isn't approved)?
6. Does source diversity exist across the clip package (multiple distinct sources), consistent with the discovery skill's own scoring signal?

## Output

```yaml
qc_report:
  qc_type: retention   # this report covers both retention and reused_content sections
  pass: boolean
  findings:
    - finding: string
      severity: low | medium | high | blocking
      section_id: string | null
      required_fix: string
  transformation_notes: string
  overall_risk_level: low | medium | high | unknown
```
An unapproved audio asset, or a plan that is in substance a re-edit of one existing source, is a
`blocking` finding — `pass: false` regardless of retention strength.

## Decision rules

- Do not pass a retention-strong plan that carries high reused-content risk, and do not pass a
  low-risk plan that fails basic retention/professionalism — both checklists must pass together.
- A single dominant source isn't automatically disqualifying (some legitimate stories only have one
  strong source video), but it raises the bar for how much original transformation the plan must add.

## Failure modes to avoid

- Treating "it has captions and music" as sufficient transformation
- Approving a plan because it's emotionally effective while ignoring source concentration risk
- Missing an unapproved audio asset because the audio-specific QC pass already ran (re-check anyway — this is the last gate before delivery)

## Handoff

Output: final `qc_report`. If `pass: true`, the plan is ready for
`hermes-football-memory-learning` and delivery to OpenMontage rendering. If `pass: false`, loop
back to the relevant upstream skill per each finding's `required_fix`.

## References

- `shared/references/reused-content-thresholds.md` — shared dominant-source thresholds used by all reused-content checks

- `shared/references/pro-editing-methodology.md` — the pre-finalization checklist this skill formalizes into a pass/fail gate

## v3 Full Editorial QA

Read `shared/references/editorial-journey/quality-assurance.md` before passing a final plan. QA has four gates: technical QA, editorial QA, platform QA, and final vibe check. Blocking issues should loop back to the correct earlier stage, not be patched superficially.

Use the re-cut rule: weak fall, unclear turning point, payoff that does not land, severe runtime mismatch, or a weak middle clip killing escalation require re-cut/selection changes, not cosmetic fixes.

## V5 patch addendum — rights risk and export gate

Before final delivery, require a `footage_rights_risk_record` for risky sports footage and an export pass from `football-platform-export-validator`.

Do not treat `usable_with_risk` as `legal_safe`; it means the user must understand the risk. A plan can be editorially strong and still blocked for user confirmation because of rights risk.

Reject any final plan that contains unverified current-event facts, fake measured values, or memory claims without provenance.

## V6 patch addendum — unified reused-content threshold

Use `shared/references/reused-content-thresholds.md` for dominant-source concentration. If one third-party source exceeds 40% of runtime, trigger `football-footage-rights-transformative-risk-assessor` and require a replacement/rationale. If it exceeds 60%, default to `avoid` or `user_must_supply_rights` unless the source is user-owned/licensed or private/internal testing only.
