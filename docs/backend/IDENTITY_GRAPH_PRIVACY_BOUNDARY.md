# Identity Graph privacy boundary

The product name “Identity Graph” must not expand backend scope into consumer/person identity.

The PreM3 Identity Graph models marketing execution identities and business marketing entities. It does not model or persist individual consumer/person identity.

This graph maps **marketing execution objects**. It does not ingest or persist:

- email
- phone
- hashed email / hashed phone
- `user_pseudo_id`
- `user_id`
- CRM person/customer ID
- device ID
- IP address
- cookie ID
- raw audience membership
- individual-level audience membership
- member lists, hashed member lists, membership snapshots
- mobile advertising IDs (`idfa`, `gaid`)

Contracts use `extra="forbid"` plus `reject_identity_graph_payload`. Those fields raise `PERSON_IDENTITY_FORBIDDEN`.

Also prohibited:

- budget / spend fields (`planned_spend`, `budget`, `actual_spend`, `recommended_spend`)
- GA4 event-scale rows (`events`, `event_rows`, `ga4_events`, `event_data`)

**Audience / Persona ledgers (IG-02A)**

ALLOWED: audience identity, audience definition metadata, persona definition, market scope, campaign relationships, provider/platform mapping refs, measurement/data-asset refs.

PROHIBITED: all person identifiers above, plus audience members, member lists, size/match-rate/reach, and research-authoring prose fields.

See [AUDIENCE_PRIVACY_BOUNDARY.md](AUDIENCE_PRIVACY_BOUNDARY.md).

`cmp_` campaign IDs and default `utm_id` values are **non-secret** machine identifiers. They are safe to copy into tracking templates. They are not credentials.

MTA `IdentityStrategy` (journey subject policy) is a different concept. Keep the names distinct.
