# Meridian skill compatibility report

Compatibility compares the pinned skill snapshot commit against released
runtime `google-meridian==1.8.0`. Upstream `main` is never installed.

Generate: `app.modeling.mmm.compatibility.generate_compatibility_report()`.

## Pin

- Upstream commit: `8ca83f6b2ffd0230264bc3e3e968b1f0a1c4f9d7`
- Runtime: `1.8.0`
- License: Apache-2.0

## Classes

| Class | Meaning |
|---|---|
| `COMPATIBLE` | Public API matches the pinned runtime |
| `COMPATIBLE_WITH_ADAPTATION` | Usable after PreM3 typed translation |
| `INCOMPATIBLE` | Must not execute blindly |
| `REFERENCE_ONLY` | Registered for a later mission / unreleased |

The report may be `compatible=true` when the only INCOMPATIBLE check is the known
skill-template mismatch (`media_effects_dist='roi'`), because PreM3 never
executes that template.

## Known mismatches

### `media_effects_dist='roi'`

Skill `model_spec_template.md` shows `ModelSpec(media_effects_dist='roi')`.

Runtime 1.8.0:

- `media_effects_dist`: `normal` \| `log_normal`
- `media_prior_type` / `rf_prior_type`: `roi` \| `mroi` \| `contribution` \| `coefficient`

Disposition: detect in the compatibility suite; compile against the current API;
prefer `media_prior_type` / `rf_prior_type` on new plans. Do not confuse
`media_effects_dist` with prior type. Do not use deprecated combined
`paid_media_prior_type` on new plans.

### Doc-consultant `/docs` tree

The documentation map references `docs/pre-modeling/...` (and related paths).
The reviewed public repo does not expose a root `/docs` directory.

Disposition: `COMPATIBLE_WITH_ADAPTATION`. Ontology only. Record the source kind
actually used.

### Unreleased upstream main

Marked `UPSTREAM_UNRELEASED` and not used in production 1.8.0 behavior:

- ModelContext channel inspection
- Analyzer incremental outcome APIs
- WeeklyOptimizationGrid
- `currency_code`

## Validated public APIs (1.8.0 table)

When `google-meridian` is not installed (unit CI), checks use the pinned API
table. When it is installed (worker image), reflection inspects:

`DataFrameInputDataBuilder`, `ModelSpec`, `PriorDistribution`, `Meridian`,
`sample_prior`, `sample_posterior`, `MeridianEDA`, `meridian_serde.save_meridian`,
`meridian_serde.load_meridian`, `reviewer.ModelReviewer`, `summarizer.Summarizer`.

Registered reference-only: `optimizer.BudgetOptimizer`, scenario planner proto
APIs.

## 1.8.0 runtime notes

Relevant released areas: `reconstruction_batch_size`, TensorFlow 2.21 family,
non-ROI ModelReviewer fixes, AKS fixes, prior dtype validation, serde
compatibility. Production worker pins `google-meridian==1.8.0` and does not
install upstream main.
