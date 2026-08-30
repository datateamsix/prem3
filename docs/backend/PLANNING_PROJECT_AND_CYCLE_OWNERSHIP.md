# Planning Project and Measurement Cycle ownership

The Investment Plan is owned by the Project (`project_id` / `workspace_id` alias). It is not owned by a Dataset, Evaluation, MMM run, or Measurement Cycle.

A Measurement Cycle may pin plan and snapshot refs. It must not store annual allocation values.

Capability mapping:

- Investment Plan → existing `Feature.PLANNING_RUN`
- Portfolio view → existing `Feature.PORTFOLIO_VIEW`
- Budget optimization → existing `Feature.BUDGET_OPTIMIZATION`

Project Home exposes `INVESTMENT_PLAN` as optional `AVAILABLE_TO_CONFIGURE`. It is not blocked by `MODEL_READY`. Budget optimization remains `NEEDS_ACCEPTED_MODEL` until an accepted MMM exists.
