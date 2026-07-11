# Reused-Content Thresholds

Use this shared threshold file in both `football-retention-quality-control` and `football-footage-rights-transformative-risk-assessor` so the system does not scatter reused-content rules across skills.

## Dominant-source concentration

- `<= 25%` from one third-party source: lower concentration risk, still verify transformation.
- `> 25% and <= 40%`: medium concentration risk; require stronger narration/structure/context transformation.
- `> 40%`: high concentration risk; trigger `football-footage-rights-transformative-risk-assessor` and require explicit rationale or source replacement.
- `> 60%`: default recommendation is `avoid` or `user_must_supply_rights`, unless the source is user-owned/licensed or the project is private/internal testing.

## Important distinction

These thresholds are editorial/reused-content risk gates, not legal clearance. A short clip can still be risky, and a long clip can still be licensed. Record `rights_status`, `transformation_notes`, and provenance separately.
