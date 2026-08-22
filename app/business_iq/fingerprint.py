"""Canonical Business IQ fingerprint. Snapshots pin this exact digest."""

from __future__ import annotations

import hashlib
import json

from app.business_iq.contracts import BusinessProfile


def profile_fingerprint(profile: BusinessProfile) -> str:
    payload = profile.model_dump(mode="json", exclude={"fingerprint", "updated_at", "current_snapshot_id"})
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
