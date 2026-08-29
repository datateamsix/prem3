# PreM3 extended EDA architecture

Official Meridian tells PreM3 what it observed. PreM3 explains why it matters.
Model Design determines what should change. The human governs consequential
choices.

The official report is evidence. The PreM3 report is intelligence. Never
collapse the two.

## Two artifacts

| Artifact | Owner | Role |
|---|---|---|
| `meridian_eda_report.html` | Official Meridian | Unaltered, immutable, SHA-256 fingerprinted source report |
| `PreM3ExtendedEDAReport` | PreM3 | Typed, business-aware, action-oriented analysis |

Do not rewrite or reskin the official HTML in backend storage. Frontend may
show `[ PreM3 Analysis ] [ Official Meridian Report ]` with PreM3 Analysis as
the default product experience.

Do not scrape Meridian HTML as truth. `MeridianEDAReceipt` remains the
authoritative structured evidence. `evaluate_meridian_eda_gate` remains
authoritative for ERROR / ATTENTION / INFO and MODEL_READY impact.

## Reused primitives

Unchanged:

- `MeridianEDAReceipt`, compact findings, data adequacy, prior context, EDA ModelSpec
- `MeridianEDASeverity`, `evaluate_meridian_eda_gate`
- `MeridianUserFeedback` as the resolution / retry / blocking primitive
- official HTML persistence, idempotency, fingerprints
- `M3EDAAnalysis` / `accept_eda_analysis` (legacy fallback; not replaced)

Relationship:

```text
MeridianEDAReceipt → Gate → MeridianUserFeedback
MeridianEDAReceipt + Business IQ + Data Foundation + knowledge
  → PreM3ExtendedEDAReport
```

The extended report cannot change readiness. Agent interpretation failure is
`PARTIAL` or `FAILED_INTERPRETATION`. Official EDA, the receipt, the gate, and
MODEL_READY behavior remain valid.

## Compiler

`compile_extended_eda_report(...)` in `app/eda/compiler.py`:

1. Validate official source / HTML SHA / receipt fingerprint.
2. Select material findings (all ERROR and ATTENTION; selected INFO).
3. Build bounded `EDAInterpretationContext` per finding.
4. Generate eligible PreM3 interpretation (deterministic default; agent optional).
5. Validate evidence references.
6. Compile implications and recommended actions.
7. Link `MeridianUserFeedback` resolution status.
8. Compile `EDAModelDesignHandoff`.
9. Fingerprint / version.
10. Persist metadata (Firestore/control plane). Official HTML stays in object storage.

Official severity is copied, never reinterpreted. ATTENTION cannot become PASS.
ERROR cannot become REVIEW. Official ERROR remains `EDA_BLOCKED`.

## Authority

Every statement is one of:

- `OFFICIAL_MERIDIAN`
- `PREM3_INTERPRETATION`
- `PREM3_RECOMMENDATION`
- `HUMAN_DECISION_REQUIRED`

Business IQ and Data Foundation facts are labeled `BUSINESS_IQ_CONTEXT` and
`DATA_FOUNDATION_CONTEXT`. They are not Meridian findings.

Agent may generate interpretation, why it matters, implication, recommended
action, alternatives, and uncertainty. Agent may not generate official
severity, official findings, MODEL_READY, data-adequacy numbers, or source
fingerprints.

## Versioning

Each report version binds:

- EDA receipt fingerprint
- official HTML SHA-256
- ModelReady fingerprint
- BusinessProfile snapshot ID
- Data Foundation fingerprint
- intelligence / knowledge version
- interpretation-policy version (`extended-eda/v1`)

Same inputs are idempotent. A material change creates a new version.
Historical reports remain immutable. Reinterpretation with current knowledge,
if added later, must create an explicit new version.

## Trusted official HTML

Class `TRUSTED_GENERATED_MERIDIAN_HTML` is provenance, not a script-free
guarantee. `official_html_ref` and `official_html_sha256` identify the same
bytes. A live `gs://` URI cannot bind the local HTML fixture. Arbitrary
uploaded customer HTML must never use this embed path. See
`docs/backend/PREM3_EDA_REPORT_FRONTEND_CONTRACT.md`.
