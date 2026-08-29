# Extended EDA frontend contract

Frontend renders the typed report. It must not reconstruct interpretation or
readiness logic.

## Read model

```
GET /v1/projects/{project_id}/cycles/{cycle_id}/mmm/eda
```

Authenticated. Tenant comes from the verified credential, never from the
path, query, body, or headers. Requires the MMM feature.

Response:

| Field | Meaning |
|---|---|
| `status` | `COMPLETE`, `PARTIAL`, or `FAILED_INTERPRETATION` |
| `extended_report` | Full `PreM3ExtendedEDAReport` JSON |
| `official_report` | Availability, `content_type`, authorized view URL, SHA-256, artifact class |
| `latest_run` | Pre-model run id and official gate status/outcome |
| `attention` | Official review-recommended, max severity, counts |
| `next_actions` | Server-owned actions to render |

Default product tab: **PreM3 Analysis**. Second tab: **Official Meridian Report**.

Do not mutate official Google/Meridian branding. Label the HTML view
“Official Meridian Report”.

## Suggested sections (PreM3 Analysis)

1. Executive Summary
2. Meridian Readiness (official status, severity, data adequacy)
3. Findings That Matter (ERROR, ATTENTION, selected material INFO)
4. What This Means for Modeling (grouped implications)
5. Recommended Actions
6. Open Modeling Decisions
7. Evidence & Provenance
8. Official Meridian Report (authorized view, not reproduced charts)

## Next actions

Server-owned values the frontend may render:

- `PROCEED_TO_MODEL_DESIGN`
- `REVIEW_ATTENTION_FINDING`
- `RESOLVE_EDA_ERROR`
- `RETURN_TO_DATA_FOUNDATION`
- `RERUN_PREMODELING`

## Official HTML

```
GET /v1/projects/{project_id}/cycles/{cycle_id}/mmm/eda/official-html
```

Serves `TRUSTED_GENERATED_MERIDIAN_HTML` only after authorization and SHA
check. Does not expose internal GCS paths. Arbitrary uploaded customer HTML
cannot use this route (`ARTIFACT_NOT_TRUSTED`).

Embed policy for `TRUSTED_GENERATED_MERIDIAN_HTML` is derived from the
artifact, not guessed:

- Document CSP always includes `sandbox` without `allow-same-origin` or
  `allow-top-navigation`, so the official report cannot reach the parent or
  navigate the top window.
- If the official report has no scripts, `script-src 'none'` and `sandbox`
  with no tokens.
- Music Center official Meridian HTML needs Vega charts. The isolated policy
  is `sandbox allow-scripts` plus
  `script-src 'unsafe-inline' https://www.gstatic.com`,
  `style-src 'unsafe-inline' https://fonts.googleapis.com`,
  `font-src https://fonts.gstatic.com`,
  `img-src data: blob: https://www.gstatic.com`,
  and `connect-src 'none'`.
- Arbitrary uploaded customer HTML cannot use this route (`ARTIFACT_NOT_TRUSTED`).

Recommended iframe:

```html
<iframe
  title="Official Meridian Report"
  sandbox="allow-scripts"
  referrerpolicy="no-referrer"
  src="{authorized_view_url}"
></iframe>
```

Do not add `allow-same-origin` or `allow-top-navigation` to the iframe sandbox.

Typed JSON is authoritative. Optional export HTML can be generated later.
Gemini must not generate the final page HTML.
