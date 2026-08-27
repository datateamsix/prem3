# Audience privacy boundary

Persona and Audience ledgers store **definitions**, not people.

## Allowed

- Opaque `per_` / `aud_` IDs
- Names, descriptions, type/source metadata, market scope, persona links, parent audience, dates, owner metadata
- Metadata pointers (`source_ref`, `business_segment_ref`, `business_profile_snapshot_id`) that do not contain SQL or person identifiers

## Prohibited (walker names fields, never values)

Person-identity keys include: `email`, `phone`, hashed contact fields, `user_id`, `user_pseudo_id`, CRM person IDs, device/cookie/IP identifiers, `audience_members`, `membership`, `member_list`, `hashed_member_list`, `membership_snapshot`, `mobile_advertising_id`, `idfa`, `gaid`.

Performance/size keys include: `estimated_size`, `match_rate`, `member_count`, `eligible_size`, `reach`, plus existing campaign performance fields.

Budget and event-scale rows remain prohibited.

Rejection messages name **fields**, never submitted values.

`CUSTOMER_LIST` is an `AudienceType`. It does not authorize storing members.

Owner `owner_ref` may hold a Clerk user id as **ownership metadata**. The graph must not persist a `user_id` field or CRM person IDs.
