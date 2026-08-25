"""Channel registry asset presence tests (logic lands in M5-01)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_channel_registry_asset_exists() -> None:
    path = REPO_ROOT / "assets" / "channels" / "channel_registry_v1.yaml"
    assert path.is_file()


def test_channel_grouping_rules_asset_exists() -> None:
    path = REPO_ROOT / "assets" / "channels" / "channel_grouping_rules_v1.yaml"
    assert path.is_file()
