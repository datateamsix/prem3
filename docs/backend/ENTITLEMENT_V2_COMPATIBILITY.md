# Entitlement v2 compatibility

Existing `Feature` values are unchanged. Additive families:

`foundation`, `mmm`, `mta`, `forecasting`, `scenario_simulation`, `budget_optimization`, `decision_intelligence`, `portfolio_view`, `api_access`

`team_seats` already existed.

## Plan meaning

| Plan | Active Projects | Notes |
|---|---|---|
| planner | 0 | No paid Project slot |
| project | 1 | One methodology-neutral PreM3 Project |
| portfolio | 10 | Adds `portfolio_view` |
| enterprise | 50 | Adds `portfolio_view` and `api_access` |

Commercial capacity is unchanged.

## Old snapshots

If a stored snapshot lacks the new feature strings but `plan_id` is a paid plan, capability mapping still entitles Foundation / MMM / MTA / Forecasting / planning families. Planner remains unentitled.

Stripe projection writes new snapshots with the expanded feature set on the next material change.
