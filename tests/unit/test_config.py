from app.config import load_settings


def test_vertex_location_and_cloud_region_are_distinct(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "global")
    monkeypatch.setenv("GOOGLE_CLOUD_REGION", "us-central1")
    settings = load_settings()
    assert settings.vertex_location == "global"
    assert settings.cloud_region == "us-central1"
    assert settings.vertex_location != settings.cloud_region


def test_cloud_region_does_not_fall_back_to_vertex_location(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "global")
    monkeypatch.delenv("GOOGLE_CLOUD_REGION", raising=False)
    settings = load_settings()
    assert settings.vertex_location == "global"
    assert settings.cloud_region == "us-central1"


def test_firestore_database_defaults_to_default_native_database(monkeypatch) -> None:
    monkeypatch.delenv("FIRESTORE_DATABASE", raising=False)
    settings = load_settings()
    assert settings.firestore_database == "(default)"


def test_firestore_database_reads_explicit_override(monkeypatch) -> None:
    monkeypatch.setenv("FIRESTORE_DATABASE", "(default)")
    settings = load_settings()
    assert settings.firestore_database == "(default)"


def test_firestore_database_strips_quoted_and_encoded_default(monkeypatch) -> None:
    monkeypatch.setenv("FIRESTORE_DATABASE", '"(default)"')
    assert load_settings().firestore_database == "(default)"
    monkeypatch.setenv("FIRESTORE_DATABASE", "%28default%29")
    assert load_settings().firestore_database == "(default)"
