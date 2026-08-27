# Campaign tracking instructions

IG-02 generates copyable tracking instructions. It does not observe live traffic and does not write to Google Ads, Meta, DV360, or GA4.

## Canonical identity

`utm_id = campaign_id`

That binding is minted on create (`parameter_name=utm_id`, `parameter_value=<campaign_id>`, `tracking_kind=PREM3_UTM_ID`). Rename does not change `utm_id`.

`recommended_utm_campaign` / display `utm_campaign` may follow the campaign name. They are not identity.

## Instruction payload

| Field | Rule |
|---|---|
| `parameter_name` | `utm_id` |
| `parameter_value` | `campaign_id` |
| `recommended_utm_campaign` | display suggestion |
| `query_parameters` | includes `utm_id` and `utm_campaign` |
| `implementation_status` | customer-facing honesty |
| `generation_provenance` | internal `GENERATED` only |
| `instruction_authority` | `PREM3_GENERATED` |
| `generated_at` / `fingerprint` | audit |

## Implementation status (honest)

| Status | Meaning in IG-02 |
|---|---|
| `NOT_IMPLEMENTED` | Instruction exists; execution is not observed. Create returns this. |
| `DECLARED_IMPLEMENTED` | Customer declared they applied the instruction. Not live evidence. |
| `OBSERVED` | Rejected in IG-02. Requires IG-03 evidence. |
| `VERIFIED` | Rejected in IG-02. Requires IG-03/IG-04 evidence. |
| `REVIEW_REQUIRED` | Conflict or incomplete evidence. |

IG-00 `GENERATED` is not a customer-facing verified state.

## Intended vs observed (IG-03 / IG-04)

- **Intended:** PreM3 generated `utm_id=<campaign_id>` for the customer to implement.
- **Observed:** the parameter is seen in GA4 / BigQuery export rows (IG-03/IG-04).
- **Verified:** intended value matches observed value under a governed check (IG-03/IG-04).

Do not collapse these. Copying instructions is not observation.

## Provider binding seam (IG-03)

`CampaignExternalBinding` may later record `(provider_id, external_account_id, external_campaign_id)`. That provider campaign ID is provenance. It never replaces `campaign_id`. IG-02 does not discover or write provider campaigns.

## API

`GET /v1/projects/{project_id}/identity-graph/campaigns/{campaign_id}/tracking`
