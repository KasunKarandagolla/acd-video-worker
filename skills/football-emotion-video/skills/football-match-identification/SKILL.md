---
name: football-match-identification
description: Use when the user refers to a current, latest, or recent football match without specifying exact details — e.g. "the latest Argentina game", "Ronaldo's last match", "the Champions League final last week". Activates to resolve vague temporal references into exact match identifiers (competition, teams, date, score, key events) before any downstream skill uses those facts. Does not verify live scores via API — produces a `match_fact_lock` artifact for human verification.
---

# Football Match Identification

Resolves vague temporal references ("latest", "recent", "last week") into exact, verifiable match metadata so downstream skills don't hallucinate facts.

## When to use this

- User mentions a current/latest/2024+ match without exact identifier
- Any downstream skill needs `match_fact_lock` before using match facts
- Current-event fact gate (`shared/references/current-event-fact-lock.md`) requires it

## Required inputs

- User's vague reference (e.g., "Messi's last World Cup game")
- Current date (from system/context)

## Workflow

1. Parse the user's reference to extract: player/team, competition hint, temporal hint ("latest", "recent", "2024 final").
2. Search available knowledge (Hermes session history, web search via `browser` tool if available, internal knowledge cutoff) for candidate matches.
3. For each candidate, build a `match_fact_lock` artifact (see `shared/contracts/pipeline-artifacts.md`):
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
   ```
4. **Critical**: The `status` field MUST be `user_confirmation_required` for any match within the last 30 days or any "latest/recent" claim. There is NO live sports API in Hermes. Do not claim `verified` for current events without explicit user confirmation.
5. If multiple candidates exist (e.g., "Ronaldo last match" — could be club or country), set `status: ambiguous` and list all candidates with distinguishing details.
6. Present the `match_fact_lock` to the user for confirmation before any downstream skill uses the facts.
7. Only after user confirms `status: verified` may downstream skills treat the facts as locked.

## Rejection rules

- Do not use internal knowledge cutoff as "verification" for current events.
- Do not set `status: verified` for any match date > (today - 30 days) without explicit user confirmation.
- Do not invent scores, key events, or player stats.

## Handoff

Output: `match_fact_lock`. Next skill: any skill requiring match facts (they must check `status: verified` before proceeding).

## References

- `shared/references/current-event-fact-lock.md`
- `shared/references/fact-provenance-standard.md`
- `shared/references/live-tournament-sourcing.md`
