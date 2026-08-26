# MTA Decision Intelligence Contract

Deterministic compiler only. No LLM narrative in M5-02.

`MTADecisionIntelligenceBrief` contains:

- `verified_findings` (`VERIFIED`) reproducible from snapshot metrics
- `interpretations` (`INTERPRETATION`)
- `recommendations` (`RECOMMENDATION`) each with evidence plus counter-evidence or uncertainty
- `decision_requirements` (`DECISION_REQUIRED`) only for mapping / Direct / Shapley / observability / comparison choices

Allowed: review Direct policy, investigate early-path presence, consider an
incrementality experiment where sensitivity is high, review Shapley path limits.

Prohibited from MTA alone: budget reallocation, spend increases/cuts, causal
incrementality, “true contribution”, or lift claims.

A brief policy version change creates a new brief, not a new `MTAResultsSnapshot`.
