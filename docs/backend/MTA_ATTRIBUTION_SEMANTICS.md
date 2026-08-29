# MTA Attribution Semantics (M5-00)

## What MTA answers

Given the interactions we can observe and the attribution assumptions we choose,
how is conversion credit distributed across channels?

## What MTA does not answer

What incremental outcomes would disappear if marketing stopped?

## Forbidden MTA product language

- causal contribution
- incremental contribution
- true contribution
- true channel impact

## Models

Heuristic models (First/Last/Linear/Time Decay/Position) expose assumptions
explicitly. They are not benchmarks of truth.

Markov and Shapley are algorithmic models over observed journeys. Shapley is
compute-bounded and requires preflight. Neither is causal incrementality.

## Future reconciliation

Preserve canonical Business IQ channel IDs so MMM ↔ MTA alignment can come later
(M5-03). Do not implement cross-method reconciliation in M5-00.
