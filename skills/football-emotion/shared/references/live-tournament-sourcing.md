# Live-Tournament / Recency-Weighted Sourcing

Use this when the event is live, very recent, or still developing.

## Recency modes

```yaml
recency_mode:
  event_age: live | under_24h | 24_72h | 3_7d | 7_30d | archive
  source_priority:
    - official_match_center_or_result_page
    - official_highlights
    - broadcaster_clips
    - press_conference_or_interview
    - verified_fan_reactions
    - social_sentiment_references
  resourcing_schedule:
    - immediate_pass
    - 72h_rescan
    - 7d_rescan
    - 30d_archive_pass
```

## Important rule

Do not trigger the normal `50 mediocre candidates means theme weak` rule too early for fresh events. For recent matches, weak results may mean sources have not been uploaded yet.

## Output states

```yaml
source_availability_status: sufficient | thin_but_usable | rescan_later | blocked
```
