# Current-Event Fact Lock

Use this before creative planning whenever the request depends on a recent, current, future, vague, or unspecified real match.

## Trigger terms

- latest / most recent / current / today / yesterday
- World Cup 2026 or any future/current tournament
- title names a team but not opponent/date
- user asks for a real match but does not provide footage

## Rule

Do not begin a final edit plan until `match_fact_lock.status = verified`.

If not verified, produce only:

```yaml
planning_mode: hypothesis_only
blocked_final_claims:
  - exact opponent
  - exact score
  - exact scorer/minute
  - exact timestamp
  - exact clip score
```

## Safe behavior

- Ask the user to confirm the match, or
- run live sourcing/search in the execution environment, or
- create a clearly labeled hypothesis plan.
