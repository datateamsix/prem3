# MTA Run Receipts and Provenance

`MTARunReceipt` is fingerprinted compact Firestore metadata:

- run / execution plan IDs  
- input contract fingerprint  
- counts (sessions/touchpoints/journeys/grouped paths)  
- model statuses  
- output refs + readback status  
- limitations  
- source commit SHA / worker image digest  

Large journeys stay in BigQuery. SUCCEEDED requires journey compile success, required models, required outputs written + read back, manifest verified, receipt persisted. Optional Shapley skip is allowed only when the plan made Shapley optional/guarded.
