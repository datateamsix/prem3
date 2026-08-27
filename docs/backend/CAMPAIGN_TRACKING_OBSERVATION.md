# Campaign tracking observation

Identity Graph stores **metadata** about observed identifiers, not event or session rows.

## TrackingObservation

`observation_id`, tenant/project, required `source_ref`, `source_kind`, `observed_at`, identifier snapshot (`identifier_kind`, optional `parameter_name`, `parameter_value`), optional provider tuple, optional `candidate_campaign_id`, `observation_status`, `evidence_fingerprint`.

Empty `source_ref` is rejected (`SOURCE_REF_REQUIRED`). The privacy walker rejects `ga4_events` / `event_rows` and person keys. There is no `put_events` and no bulk raw-event ingest API.

## Declared vs observed vs verified

- **Declared:** campaign configuration says tracking should exist (`NOT_IMPLEMENTED` / `DECLARED_IMPLEMENTED`).
- **Observed:** a governed `source_ref` recorded an identifier.
- **Verified:** that identifier uniquely resolves to the expected canonical campaign.

Observation never mutates Campaign Ledger markets, channels, flight dates, persona/audience targets, or names.

## Sources

GA4 BigQuery, Google Ads, DV360, SA360, CM360, customer registry, custom BigQuery, or manual refs. Data Foundation owns where evidence lives; Identity Graph owns what the identifier means.
