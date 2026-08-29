"""Versioned Music Center SYNTHETIC_DEMO fixture v2 — later date range only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from random import Random

from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mta.contracts import AttributionModelId
from app.modeling.mta.synthetic_music_center import SyntheticEventSpec

FIXTURE_ID = "music_center_mta_demo_v2"
FIXTURE_VERSION = "v2"
WINDOW_START = date(2024, 9, 1)
WINDOW_END = date(2024, 9, 30)
GENERATION_SEED = 20240901
CONVERSION_EVENT = "purchase"

DEMO_ATTRIBUTION_MODELS: tuple[AttributionModelId, ...] = (
    AttributionModelId.FIRST_TOUCH,
    AttributionModelId.LAST_TOUCH,
    AttributionModelId.LAST_NON_DIRECT,
    AttributionModelId.LINEAR,
    AttributionModelId.TIME_DECAY,
    AttributionModelId.POSITION_BASED,
    AttributionModelId.MARKOV,
    AttributionModelId.SHAPLEY,
)

# source, medium, campaign → Channel Registry V1 via channel_grouping_v1
TRAFFIC = {
    "search_paid": ("google", "cpc", "brand_exact"),
    "search_organic": ("google", "organic", "(organic)"),
    "social_paid": ("facebook", "cpc", "prospecting"),
    "display": ("google", "display", "retarget"),
    "email": ("email", "email", "newsletter"),
    "direct": (None, None, None),
    "ai_search_chatgpt": ("chatgpt.com", "referral", "ai_answer"),
    "ai_search_perplexity": ("perplexity.ai", "referral", "ai_answer"),
    "ai_search_gemini": ("gemini.google.com", "referral", "ai_answer"),
    "sparse_sms": ("twilio", "sms", "rare_alert"),
}

ARCHETYPES: tuple[tuple[str, ...], ...] = (
    ("social_paid", "search_organic", "search_paid"),
    ("display", "search_organic", "direct"),
    ("email", "direct"),
    ("ai_search_chatgpt", "search_organic", "search_paid"),
    ("search_paid",),
    ("search_organic",),
    ("social_paid", "display", "search_paid"),
    ("ai_search_perplexity", "email", "search_paid"),
    ("ai_search_gemini", "search_organic", "direct"),
    ("display", "social_paid", "search_organic", "search_paid", "direct"),
    ("direct",),
)


@dataclass(frozen=True)
class MusicCenterMTADemoFixture:
    fixture_id: str
    fixture_version: str
    evidence_authority: str
    source_type: str
    source_project: str
    source_dataset: str
    date_range_start: str
    date_range_end: str
    conversion_event: str
    expected_channels: tuple[str, ...]
    expected_conversion_count: int
    generation_seed: int
    channel_registry_version: int
    channel_grouping_version: int
    fixture_fingerprint: str


def _touch(
    *,
    day: date,
    user: str,
    session: int,
    channel_key: str,
    event_name: str,
    hour: int,
    txn: str | None = None,
    revenue: float | None = None,
) -> SyntheticEventSpec:
    source, medium, campaign = TRAFFIC[channel_key]
    return SyntheticEventSpec(
        event_date=day,
        event_name=event_name,
        user_pseudo_id=user,
        ga_session_id=session,
        source=source,
        medium=medium,
        campaign=campaign,
        transaction_id=txn,
        purchase_revenue=revenue,
        hour=hour,
    )


def music_center_v2_events(*, seed: int = GENERATION_SEED) -> list[SyntheticEventSpec]:
    rng = Random(seed)
    events: list[SyntheticEventSpec] = []
    repeats = {
        0: 10,
        1: 8,
        2: 8,
        3: 8,
        4: 10,
        5: 10,
        6: 8,
        7: 6,
        8: 6,
        9: 5,
        10: 8,
    }
    user_n = 0
    session = 10_000
    for arch_idx, path in enumerate(ARCHETYPES):
        for _copy in range(repeats[arch_idx]):
            user_n += 1
            user = f"mc_v2_{user_n:04d}"
            start_offset = rng.randint(0, 20)
            gaps = [rng.choice([0, 1, 2, 4, 8, 12]) for _ in path]
            day = WINDOW_START + timedelta(days=start_offset)
            hour = rng.randint(8, 20)
            for step, channel_key in enumerate(path):
                day = min(WINDOW_END, day + timedelta(days=gaps[step]))
                session += 1
                events.append(
                    _touch(
                        day=day,
                        user=user,
                        session=session,
                        channel_key=channel_key,
                        event_name="session_start",
                        hour=hour,
                    )
                )
                events.append(
                    _touch(
                        day=day,
                        user=user,
                        session=session,
                        channel_key=channel_key,
                        event_name="page_view",
                        hour=min(23, hour + 1),
                    )
                )
            session += 1
            last = path[-1]
            events.append(
                _touch(
                    day=day,
                    user=user,
                    session=session,
                    channel_key=last,
                    event_name="purchase",
                    hour=min(23, hour + 2),
                    txn=f"txn_v2_{user_n:04d}",
                    revenue=float(40 + (user_n % 17) * 7),
                )
            )
    # Intentional sparse / limited condition (sms → other via UDF).
    events.append(
        _touch(
            day=WINDOW_START + timedelta(days=3),
            user="mc_v2_sparse",
            session=99_001,
            channel_key="sparse_sms",
            event_name="session_start",
            hour=9,
        )
    )
    events.append(
        _touch(
            day=WINDOW_START + timedelta(days=3),
            user="mc_v2_sparse",
            session=99_001,
            channel_key="sparse_sms",
            event_name="purchase",
            hour=10,
            txn="txn_v2_sparse",
            revenue=15.0,
        )
    )
    return events


def fixture_contract(*, project_id: str = "modelready-m3") -> MusicCenterMTADemoFixture:
    events = music_center_v2_events()
    purchases = [e for e in events if e.event_name == "purchase"]
    payload = {
        "fixture_id": FIXTURE_ID,
        "fixture_version": FIXTURE_VERSION,
        "seed": GENERATION_SEED,
        "window": [WINDOW_START.isoformat(), WINDOW_END.isoformat()],
        "event_count": len(events),
        "purchase_count": len(purchases),
    }
    return MusicCenterMTADemoFixture(
        fixture_id=FIXTURE_ID,
        fixture_version=FIXTURE_VERSION,
        evidence_authority="SYNTHETIC_DEMO",
        source_type="SYNTHETIC_GA4_BIGQUERY",
        source_project=project_id,
        source_dataset="analytics_music_center_synthetic",
        date_range_start=WINDOW_START.isoformat(),
        date_range_end=WINDOW_END.isoformat(),
        conversion_event=CONVERSION_EVENT,
        expected_channels=(
            "search_paid",
            "search_organic",
            "social_paid",
            "display",
            "email",
            "direct",
            "ai_search",
        ),
        expected_conversion_count=len(purchases),
        generation_seed=GENERATION_SEED,
        channel_registry_version=1,
        channel_grouping_version=1,
        fixture_fingerprint=canonical_fingerprint(payload),
    )
