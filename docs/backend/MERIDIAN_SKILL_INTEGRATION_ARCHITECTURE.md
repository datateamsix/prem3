# Meridian skill integration architecture

PreM3 uses official Google Meridian agent skills as **upstream modeling
knowledge and workflow guidance**. Skills are not trusted production executors.

```text
Pinned upstream skill snapshot
        ↓
Compatibility review
        ↓
PreM3 typed internal adaptation
        ↓
Deterministic compiler
        ↓
Approved execution plan
        ↓
Known Meridian worker
```

Prohibited: `npx skills add google/meridian` → agent-authored Python → production
execution.

## Pin

| Field | Value |
|---|---|
| Repository | `google/meridian` |
| Reviewed commit | `8ca83f6b2ffd0230264bc3e3e968b1f0a1c4f9d7` |
| Released runtime | `google-meridian==1.8.0` |
| License | Apache-2.0 |
| Snapshot | `third_party/google_meridian/<commit>/` |

Production never fetches GitHub. New Google commits require an explicit sync into
a **new** immutable snapshot directory, compatibility suite, human review, and
internal version promotion. Assets are never overwritten in place.

## Skill roles (Mission 3)

| Skill | Role |
|---|---|
| `meridian-doc-consultant` | Active adaptation: topic ontology + source-kinded retrieval |
| `meridian-model-building` | Active adaptation: design brief, decisions, compiler, worker |
| `meridian-result-visualization` | Active adaptation: official reviewer + summarizer via worker |
| `meridian-budget-optimization` | Register / pin / compatibility only. Not executed. |
| `meridian-scenario-planner` | Register / pin / compatibility only. Not executed. |

`MODEL_ACCEPTED`, not `MODEL_READY`, unlocks later optimization/scenario
availability. Execution of those skills is a later mission.

## Checkpoint translation

Upstream interactive `ask_question` pauses become durable PreM3
`ModelDecision` / `FitApproval` / `ModelAcceptanceApproval` records: typed,
user-attributed, timestamped, fingerprint-bound.

## Model-building adaptations

| Upstream skill | PreM3 |
|---|---|
| Prompt for paths | Server-resolved destinations |
| Heuristic CSV mapping | Verified `ModelReadyManifest` mapping |
| ModelSpec prompt | Design Brief + durable decisions |
| EDA | Official pre-modeling EDA already complete; final `sample_prior` is separate |
| MCMC prompt | `MeridianFitPlan` + human approval |
| Generated Python | Known pinned worker |
| Save model | `meridian.schema.serde.meridian_serde.save_meridian` → `meridian_model.binpb` |

## Doc-consultant adaptations

The public documentation map references repo-relative `docs/...` paths, but the
reviewed public repository has no root `/docs` tree. Treat the map as a topic
ontology. Resolve numbers from:

- `PINNED_REPO_SOURCE`
- `OFFICIAL_MERIDIAN_WEB_DOC`
- `PREM3_CURATED_MERIDIAN_CONTEXT`

If the authoritative source is unavailable, return review/unknown. Do not invent
a numeric recommendation. No live docs/GitHub fetch inside model fit.

## Progressive disclosure

Load only stage-relevant assets:

- Model Design → model-building + doc-consultant
- Model Review → result-visualization + post-modeling guidance
- Optimization later → budget-optimization skill

## Package

Modeling lives in `app/modeling/`. Do not expand `app/core/run_coordinator.py`
into a modeling monolith. Fitting is outside `prem3-api` (`prem3-meridian-model-worker`).
