# MMM Results Frontend Contract (M4-00)

## Routes

All under `/v1/projects/{project_id}/cycles/{cycle_id}/`:

| Method | Path | Response |
|---|---|---|
| GET | `mmm/results` | Render-ready results read model |
| GET | `mmm/results/channels` | Same payload (channel list) |
| GET | `mmm/results/channels/{channel_id}` | Filtered channels |
| GET | `mmm/results/response-curves` | Typed curves |
| GET | `mmm/decision-brief` | Decision Intelligence brief |

Tenant is server-resolved. No raw GCS/BQ paths are returned as authority.

## Primary read model fields

- `status` / `reason`
- `model_context` (includes `eligibility`, `model_accepted`)
- `health_summary`
- `portfolio_summary`
- `channel_results` (each metric has `availability`)
- `key_findings`
- `known_limitations`
- `next_actions`
- `provenance_summary`
- `acceptance_computed_by_server=true`
- `recommendation_eligibility_computed_by_server=true`
- `latest_result_snapshot_id` / `accepted_result_snapshot_id`

Frontend **must not** recompute acceptance, availability, or recommendation
eligibility.

## Before fit complete

```json
{
  "status": "NOT_AVAILABLE",
  "reason": "FIT_NOT_COMPLETE"
}
```

Music Center remains in this state until a real posterior completes.

## Contract generation

```bash
python scripts/export_contracts.py
python scripts/export_openapi.py
```

Frontend generates TypeScript types from committed schemas — do not hand-write mirrors.
