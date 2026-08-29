# MTA Channel-Role Intelligence

Policy version: `mta_channel_role_policy_v1`.

Classifier uses numeric features only — never channel display name.

| Label | Rule |
|---|---|
| `INTRODUCER` | first_share ≥ 0.40 and last_share ≤ 0.25 |
| `ASSISTER` | middle_share ≥ 0.40 |
| `CONVERTER` | last_share ≥ 0.40 and first_share ≤ 0.25 |
| `MULTI_ROLE` | at least two of first/middle/last ≥ 0.25 |
| `DIRECT_CAPTURE` | `channel_id=direct` and last_share ≥ 0.50 |
| `MODEL_SENSITIVE` | sensitivity HIGH or VERY_HIGH |
| `LOW_OBSERVABILITY` | presence_rate < 0.02 or presence_count < 3 (or LIMITED observability at low volume) |

Labels may stack. `LOW_OBSERVABILITY` suppresses INTRODUCER/ASSISTER/CONVERTER/MULTI_ROLE
so the system does not manufacture a confident role.

Position policy `position_policy_v1` uses `FIRST_AND_LAST`: a one-touch journey
increments both first and last counts. Shares use `converted_journey_count` as
denominator and are not a 3-way partition of 1.0.

Roles describe observed journey presence, not causal demand creation.
Direct is never treated as a media investment channel.
