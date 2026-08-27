# Audience provider equivalence

Provider audience IDs never replace `audience_id`.

`AudienceExternalBinding` is an IG-03 seam only. IG-02A does not persist, CRUD, or discover provider audience bindings. The same reserved rule applies to `AUDIENCE_BOUND_TO_EXTERNAL` edges.

## Locked assertion

The same canonical audience on multiple providers does **not** mean identical membership. There is no `membership_identical` field and no service that asserts cross-provider member equality.

IG-03 may attach provider IDs as provenance. Those bindings are not PreM3 identity and must not rewrite `CanonicalAudience.audience_id`.
