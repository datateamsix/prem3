# MTA Provisioning

`MTAProvisioningService` (`app/modeling/mta/provisioning_service.py`) owns:

1. Render-ready infrastructure plan UX (frontend does not calculate)
2. SQL asset resolve + target authority (`prem3_modeling` only)
3. Approval gate
4. UDF / DDL / scheduled-query provision
5. Dry-run where useful, then live execute
6. Read-back verify + receipts
7. Schedule disable/update via governed fingerprints

## Idempotency

| State | Action |
|---|---|
| Absent | create |
| Present + matching fingerprint/schema | reuse/verify |
| Present + conflicts immutable history | fail closed |
| Mutable alias/schedule | update only through governed action |

## APIs

- `GET /v1/channels`
- `GET .../mta/provisioning-plan` + `POST .../approve`
- `POST .../mta/scheduled-refresh/plan|provision|disable`
- `GET /v1/mta/parameter-explanations`

Caller cannot override GCP project/dataset — server resolves from binding/settings.
