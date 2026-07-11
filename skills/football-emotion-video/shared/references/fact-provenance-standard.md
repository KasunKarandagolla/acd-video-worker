# Fact Provenance Standard

Every precise claim in this pipeline must declare where it came from.

## Labels

```yaml
verified_from_source: supported by cited source, frame review, transcript, official match data, or verified user-provided source
measured_by_tool: produced by FFmpeg, OCR, scene analyzer, VAD, BPM detector, or similar tool
estimated_by_editor: an editorial estimate after reviewing material
creative_hypothesis: a proposed framing, not a factual claim
user_supplied: supplied by the user and preserved as user input
forbidden_unverified: too precise to keep without proof
```

## Forbidden without proof

- exact current-event scores/minutes/scorers
- exact clip scores before frame/audio review
- LUFS/true peak/BPM/exposure/codec/HDR claims before tools measure them
- percentage improvement claims
- legal-safe claims for third-party footage
- memory lessons pretending a hypothesis is a measured result

## Downgrade rule

If a claim is useful but unverified, downgrade it to `creative_hypothesis` or `estimated_by_editor` and keep it out of final artifacts.
