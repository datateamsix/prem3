# Optimization scenario artifact

P6-06 publishes an immutable `ScenarioArtifact` from a **completed** P6-05 `OptimizationRun`.

It is a modeled alternative to the current approved plan. It is not approved, not committed, not a forecast actual, and not provider execution state. The evidence label is `MODEL_RECOMMENDED`.

Metadata lives in Firestore (`oscn_`). Allocation rows live on customer-owned GCS `scenario_{scenario_id}`. Changing the optimizer result, baseline, constraints, model, or period creates a new scenario identity.
