# MTA DP6 1.0.11 Compatibility

Inspected source: `DP6/Marketing-Attribution-Models` tag **v1.0.11**
(`marketing_attribution_models.MAM`). PyPI latest published wheel is 1.0.10;
PreM3 pins the Git tag so production executes the claimed version.

Install:

```
marketing-attribution-models @ git+https://github.com/DP6/Marketing-Attribution-Models.git@v1.0.11
```

## Constructor (journey-row input)

`group_channels=False` — one DataFrame row per journey.

| Parameter | PreM3 binding |
|---|---|
| `channels_colname` | `channels` (list) or path string with ` > ` |
| `group_channels_by_id_list` | `["journey_id"]` |
| `journey_with_conv_colname` | `converted` |
| `conversion_value` | column `conversion_value` (frequency or value) |
| `path_separator` | ` > ` |
| `time_till_conv_colname` | omitted → DP6 synthesizes reverse-index × 24 hours |

`group_channels=True` (session-per-row grouping) is not used. PreM3 already compiles journeys.

## Heuristic methods

| PreM3 model | Exact 1.0.11 method | Required parameters |
|---|---|---|
| FIRST_TOUCH | `attribution_first_click()` | none |
| LAST_TOUCH | `attribution_last_click()` | none |
| LAST_NON_DIRECT | `attribution_last_click_non(but_not_this_channel=)` | `direct` (registry id, not DP6 default `"Direct"`) |
| LINEAR | `attribution_linear()` | none |
| TIME_DECAY | `attribution_time_decay(decay_over_time=, frequency=)` | execution-plan values; **no package defaults** |
| POSITION_BASED | `attribution_position_based(list_positions_first_middle_last=)` | `[first, middle, last]` summing to 1.0 |

Return shape: `(channels_value, frame)` where `frame` is a DataFrame with
`channels` + one credit column. Adapter converts to `ChannelCredit`.

LAST_NON_DIRECT is **native DP6**. Direct is not dropped globally; only this
model ignores the configured channel id (`direct`).

## Time Decay

DP6 package defaults (`decay_over_time=0.5`, `frequency=168`) are **not used**.
PreM3 binds `MTAAnalysisConfig` / `default_model_parameters()`:
`decay_over_time=7`, `frequency=2`.

Formula (installed source): `exp(log(decay_over_time) * floor(hours / frequency))`.

## Position Based

DP6 accepts `list_positions_first_middle_last`. PreM3 rejects weights that do
not sum to 1.0 before invocation. No silent normalize.

## Markov

`attribution_markov(transition_to_same_state=, conversion_value_as_frequency=)`

Returns `(channels_value, frame, matrix, removal_effect_result)`.

Runtime special states (do not invent START/CONVERSION/NULL):

- `(inicio)` start
- `(conversion)` absorbing conversion
- `(null)` absorbing non-conversion

These are not Channel Registry marketing IDs and are not persisted as channel credits.

`conversion_value_as_frequency=True` uses the conversion_value column as
transition counts — valid for grouped path-frequency rows.

Removal effect is modeled removal sensitivity, not causal incremental loss.

## Shapley

`attribution_shapley(size=, order=, values_col=)`

PreM3 binds `size=4`, `order=True`, `values_col="conversions"` from the
execution plan. Package defaults (`order=False`, `values_col="conv_rate"`)
are not used.

`size` truncates each journey to the last N unique channels
(`journey_conversion_table`). When any journey exceeds `size`, PreM3 records
`path_limit_applied` and `SHAPLEY_PATH_LIMIT`.

ShapleyPreflight remains mandatory. Blocked Shapley is typed unavailable.

## Frequency weighting

Grouped paths: one row per unique path, `conversion_value = occurrence count`
(or conversion value). Expanded repeated journeys must match Markov credits
within the documented share tolerance.

## Non-converting paths

`journey_with_conv=False` zeros heuristic conversion_value and routes Markov
to `(null)`. Music Center demo config keeps
`include_nonconverting_paths=false` (existing input-contract default) unless a
later config explicitly enables them.

## Numerical policy

- No NaN / ±Inf
- Attribution shares sum to 1.0 ± `1e-6` across marketing channels
- Unknown marketing channel IDs fail closed
