# MTA Results Frontend Contract

Read-only GET APIs. Tenant is server-owned; never taken from the body.

| Method | Path |
|---|---|
| GET | `/v1/projects/{project_id}/cycles/{cycle_id}/mta` |
| GET | `/v1/projects/{project_id}/cycles/{cycle_id}/mta/results` |
| GET | `/v1/projects/{project_id}/cycles/{cycle_id}/mta/results/channels` |
| GET | `/v1/projects/{project_id}/cycles/{cycle_id}/mta/results/channels/{channel_id}` |
| GET | `/v1/projects/{project_id}/cycles/{cycle_id}/mta/results/model-comparison?models=` |
| GET | `/v1/projects/{project_id}/cycles/{cycle_id}/mta/results/markov` |
| GET | `/v1/projects/{project_id}/cycles/{cycle_id}/mta/results/shapley` |
| GET | `/v1/projects/{project_id}/cycles/{cycle_id}/mta/results/journeys` |
| GET | `/v1/projects/{project_id}/cycles/{cycle_id}/mta/results/visualizations` |
| GET | `/v1/projects/{project_id}/cycles/{cycle_id}/mta/decision-brief` |

`?models=` is presentation-only.

Overview adds latest/current snapshot ids, models available, sensitivity/observability
summaries, and next actions such as `REVIEW_MTA_RESULTS` and `COMPARE_ATTRIBUTION_MODELS`.
No spend actions.

Channel detail includes observed role, position, model credits, sensitivity,
top paths containing the channel, limitations, interpretation, and evidence refs.
