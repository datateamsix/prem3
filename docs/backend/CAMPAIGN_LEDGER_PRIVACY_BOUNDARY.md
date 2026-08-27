# Campaign Ledger privacy boundary

The Campaign Ledger maps marketing execution objects. It does not map people.

## Allowed metadata

Campaign name, status, planned dates, canonical market IDs, Channel Registry IDs, owner label/ref (optional Clerk `user_id` as `owner_ref` value only), objective ref/label, empty audience/persona ID lists, tracking parameter names/values that equal `campaign_id`.

## Prohibited

Person-identity keys: `email`, `phone`, hashed contact fields, `user_id` as a payload key, `user_pseudo_id`, device/cookie/IP identifiers, `audience_members`, raw membership.

Budget keys: `budget`, `planned_spend`, `actual_spend`, `recommended_spend`.

Performance keys: `impressions`, `conversions`, `attribution`, `roas`, `cpa`, `cpc`, `clicks`, `platform_metrics`.

Event-scale rows: `events`, `ga4_events`, `event_data`.

`extra=forbid` on Identity Graph models plus the privacy walker reject these on ingest.

## Owner_ref vs user_id

`owner_type=USER` may store a Clerk `user_id` string in `owner_ref`. That is campaign ownership metadata. The graph must not persist a `user_id` field, audience members, or CRM person IDs.

## Store

Firestore Identity Graph documents contain the same metadata-only contracts. There is no events collection and no membership collection.
