"""Compile a snapshot from a completed Cloud E2E MTA dispatch (BQ read-back, in-memory persist)."""

from __future__ import annotations

import json
from pathlib import Path

from google.cloud import firestore

from app.modeling.mta.dispatch import FakeMTADispatcher
from app.modeling.mta.readback import BigQueryResultStore, InMemoryResultStore, ReadbackError
from app.modeling.mta.results_contracts import MTAEvidenceAuthority
from app.modeling.mta.runtime_bundle import bundle_journeys, hydrate_runtime_bundle
from app.modeling.mta.service import MTAService

PROJECT = "modelready-m3"
DISPATCH = "mtdsp_fe1e35c849164327"
PROOF = Path("evaluation/meridian_music_center_mta_real_dp6_cloud_e2e_proof.json")


def main() -> int:
    fs = firestore.Client(project=PROJECT)
    repo = hydrate_runtime_bundle(fs, dispatch_id=DISPATCH)
    journeys = bundle_journeys(fs, dispatch_id=DISPATCH)
    run = next(iter(repo.runs.values()))
    bq = BigQueryResultStore(project_id=PROJECT)
    mem = InMemoryResultStore()
    mem.write(f"_journeys_{run.run_id}", journeys)
    for table in (
        f"mta_attribution_channel_results_{run.run_id}",
        f"mta_run_manifest_{run.run_id}",
        f"mta_path_frequencies_{run.run_id}",
        f"mta_markov_transitions_{run.run_id}",
        f"mta_markov_removal_effects_{run.run_id}",
        f"mta_shapley_results_{run.run_id}",
    ):
        try:
            mem.write(table, bq.read_back(table))
        except ReadbackError:
            continue
    service = MTAService(repo=repo, result_store=mem, dispatcher=FakeMTADispatcher())
    compiled, brief = service.compile_results(
        run_id=run.run_id,
        evidence_authority=MTAEvidenceAuthority.SYNTHETIC_DEMO,
    )
    kinds = [v.kind.value for v in compiled.visualizations]
    proof = json.loads(PROOF.read_text(encoding="utf-8"))
    proof.update(
        {
            "result_snapshot_id": compiled.snapshot.result_snapshot_id,
            "snapshot_fingerprint": compiled.snapshot.fingerprint,
            "evidence_authority": compiled.snapshot.evidence_authority.value,
            "models_completed": list(compiled.snapshot.models_completed),
            "shapley_availability": compiled.shapley.availability.value,
            "visualization_kinds": kinds,
            "brief_id": brief.brief_id,
            "p0_viz_count": len(kinds),
            "snapshot_compile": "BQ_READBACK_IN_MEMORY",
        }
    )
    PROOF.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "snapshot": compiled.snapshot.result_snapshot_id,
                "brief": brief.brief_id,
                "computation_authority": compiled.snapshot.computation_authority.value,
                "kinds": kinds,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
