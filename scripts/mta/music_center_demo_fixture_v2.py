"""Load Music Center MTA demo fixture v2 into analytics_music_center_synthetic.

Does not overwrite the June 2024 v1 shards.
"""

from __future__ import annotations

import argparse
import json
import os

from app.modeling.mta.music_center_fixture_v2 import fixture_contract, music_center_v2_events
from app.modeling.mta.synthetic_music_center import load_synthetic_ga4_events


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project",
        default=os.environ.get("GOOGLE_CLOUD_PROJECT") or "modelready-m3",
    )
    args = parser.parse_args()
    contract = fixture_contract(project_id=args.project)
    events = music_center_v2_events()
    load_synthetic_ga4_events(project_id=args.project, events=events, replace=True)
    print(json.dumps(contract.__dict__, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
