# Channel Contract (V1)

PreM3 uses one versioned **Canonical Channel Registry** as platform authority across
Business IQ, Data Foundation, MMM, MTA, Planning, and Decision Intelligence.

## Identity hierarchy

```
channel_family_id → channel_id → provider / platform / campaign
```

Provider is not channel. Example: `provider_id=google_ads` may map traffic into
`channel_id=search_paid`.

## V1 stable channel IDs

Do not rename for aesthetics. Display names may change independently.

From `assets/channels/channel_registry_v1.yaml`:

`direct`, `search_paid`, `search_organic`, `ai_search`, `social_paid`, `social_organic`,
`video_paid`, `video_organic`, `ctv_streaming`, `tv_linear`, `display`, `shopping_paid`,
`shopping_organic`, `retail_media`, `email`, `sms`, `mobile_push`, `crm_owned`, `audio`,
`podcast`, `radio`, `affiliate`, `referral`, `influencer`, `partnership`, `ooh`, `print`,
`direct_mail`, `other_paid`, `other`

## ai_search

`channel_id=ai_search` is a true platform channel (`mmm_allowed=true`, MTA default).
It is not MTA-only UDF trivia — BIQ/MMM/Planning/DF may bind it.

## Versioning

Registry v1 is immutable. Adding channels requires registry v2. Mapping UDFs pin a
compatible registry version. Outputs not in the pinned registry fail closed.

## Customer mappings

Repo owns registry + default rules + SQL compiler. Customer control plane owns approved
`ChannelGroupingRuleSet` versions. Customer-specific mappings are not committed to git.
