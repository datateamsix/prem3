# MTA Result Authority and Provenance

Authority vocabulary (MTA-specific, mirroring M4 values without importing MMM types):

| Authority | Owner |
|---|---|
| `VERIFIED` | Deterministic runtime / snapshot metrics |
| `INTERPRETATION` | PreM3 explanation of verified evidence |
| `RECOMMENDATION` | Bounded measurement recommendation |
| `DECISION_REQUIRED` | Human measurement/configuration choice |

`MTAResultsSnapshot` fingerprints:

- run receipt fingerprint
- execution plan fingerprint
- channel registry / grouping fingerprints
- model output fingerprints
- results compiler version
- role and sensitivity policy versions

A Decision Intelligence policy change produces a new brief, not a new attribution snapshot.

Evidence authority for Music Center live proof is `SYNTHETIC_DEMO`.
