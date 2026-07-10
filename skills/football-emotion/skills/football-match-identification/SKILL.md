---
name: football-match-identification
description: >-
  Use before brief interpretation whenever a football video request references latest, most recent, current tournament, 2026 or later, an unspecified opponent, vague match identity, or a real sporting event whose facts may have changed. This skill identifies and locks the exact match, score, teams, date, key events, and unresolved uncertainties before creative planning. It blocks final edit planning when the match is ambiguous or unverified.
---

# Football Match Identification

This is the first factual gate for current or ambiguous football-event briefs. It prevents the agent from building beautiful edit plans around fake scores, fake scorers, fake timestamps, or non-existent matches.

## When to use

Use before `social-edit-reasoning` and `football-story-strategy` if the user says any of:

- latest / most recent / current / yesterday / today
- 2026 or later
- World Cup, Euros, Copa, Champions League, Premier League, or any live tournament
- a title without opponent or date, such as `Argentina's hardest victory nobody expected`

## Required output

```yaml
match_fact_lock:
  status: verified | ambiguous | not_found | user_confirmation_required
  competition: string
  match: string
  date: string
  teams: [string, string]
  score: string
  key_events:
    - minute: string
      normalized_match_time: string
      event: string
      player: string
      source_url_or_reference: string
      verification_status: verified_from_source | user_supplied | unverified
  selected_story_candidate: string
  rejected_match_candidates:
    - match: string
      rejection_reason: string
  factual_uncertainties:
    - string
  must_not_claim:
    - string
```

## Rules

1. If `status != verified`, downstream skills may produce only a hypothesis plan.
2. Do not invent exact scorers, minutes, penalties, cards, venue, or scoreline.
3. If multiple matches could fit, present candidates and ask for confirmation unless the user explicitly permits a hypothesis plan.
4. Convert stoppage time into both notation forms where possible: `90+2'` and approximate broadcast time such as `92:15`, but mark which one is measured and which one is interpreted.
5. Store unverified social claims in `factual_uncertainties`, not in the story plan.

## Handoff

- If verified: hand `match_fact_lock` to `social-edit-reasoning`.
- If ambiguous: stop at `user_confirmation_required`.
- If not found: recommend a safer title or ask the user to supply footage/details.

## V6 patch addendum — project artifact prerequisite

For project artifact validation, current-event briefs must include a `match_fact_lock` artifact before final planning. Use:

```bash
python3 tools/current_event_gate_lint.py <project_artifacts_dir>
```

If `match_fact_lock.status` is not `verified`, keep `planning_mode: hypothesis_only`. Do not copy exact examples from source packs, changelogs, simulations, or analysis files into live artifacts.
