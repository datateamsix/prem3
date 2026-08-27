# Audience provider equivalence

Provider audience IDs never replace `audience_id`.

`AudienceExternalBinding` is persisted in IG-03. The same canonical audience on multiple providers does **not** mean identical membership. There is no `membership_identical` field and no service that asserts cross-provider member equality.

Bindings are provenance. They must not rewrite `CanonicalAudience.audience_id` or store members.
