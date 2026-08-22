"""KMS-backed AES-256-GCM Google credential vault tests."""

from __future__ import annotations

import logging
from dataclasses import replace
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.exceptions import InvalidTag

from app.config import load_settings
from app.control_plane.memory import InMemoryControlPlaneRepository
from app.control_plane.models import CredentialEnvelope
from app.governance.codes import OPENID_SCOPES
from app.integrations.google.adapters import GoogleTokenSet
from app.integrations.google.vault import (
    PRODUCTION_VAULT_ALGORITHM,
    CloudKmsKek,
    ControlPlaneCredentialVault,
    FakeKmsKek,
    InMemoryCredentialVault,
)
from app.service.app import _default_google_services
from tests.unit.api_support import auth_header, seed_tenant
from tests.unit.google_support import connect_google, google_harness


def _vault(kms: FakeKmsKek | None = None):
    store = InMemoryControlPlaneRepository()
    tenant, _identity = seed_tenant(store)
    return ControlPlaneCredentialVault(repo=store, kms=kms or FakeKmsKek()), store, tenant.tenant_id


def test_production_vault_uses_aead() -> None:
    vault, _store, tenant_id = _vault()
    envelope = vault.put_refresh_token(
        tenant_id=tenant_id, credential_ref="cref_aead000000000001", refresh_token="rt-secret"
    )
    assert envelope.algorithm == PRODUCTION_VAULT_ALGORITHM
    assert envelope.algorithm != "hmac-sha256-xor-v1"
    assert envelope.nonce
    assert vault.get_refresh_token(
        tenant_id=tenant_id, credential_ref="cref_aead000000000001"
    ) == "rt-secret"


def test_production_vault_uses_kms_wrapped_dek() -> None:
    kms = FakeKmsKek()
    vault, _store, tenant_id = _vault(kms=kms)
    envelope = vault.put_refresh_token(
        tenant_id=tenant_id, credential_ref="cref_wrap000000000001", refresh_token="rt-secret"
    )
    dek = kms.decrypt(bytes.fromhex(envelope.wrapped_dek))
    assert len(dek) == 32
    assert envelope.kms_key == kms.key_resource
    assert envelope.ciphertext != "rt-secret"


def test_unique_dek_per_credential_write() -> None:
    vault, _store, tenant_id = _vault()
    first = vault.put_refresh_token(
        tenant_id=tenant_id, credential_ref="cref_dek1000000000001", refresh_token="rt-a"
    )
    second = vault.put_refresh_token(
        tenant_id=tenant_id, credential_ref="cref_dek2000000000001", refresh_token="rt-a"
    )
    assert first.wrapped_dek != second.wrapped_dek


def test_unique_nonce_per_credential_write() -> None:
    vault, _store, tenant_id = _vault()
    first = vault.put_refresh_token(
        tenant_id=tenant_id, credential_ref="cref_nce1000000000001", refresh_token="rt-a"
    )
    second = vault.put_refresh_token(
        tenant_id=tenant_id, credential_ref="cref_nce2000000000001", refresh_token="rt-a"
    )
    assert first.nonce != second.nonce
    assert first.ciphertext != second.ciphertext


def test_ciphertext_tamper_fails_authentication() -> None:
    vault, store, tenant_id = _vault()
    vault.put_refresh_token(
        tenant_id=tenant_id, credential_ref="cref_tamper0000000001", refresh_token="rt-secret"
    )
    envelope = store.get_credential_envelope(
        tenant_id=tenant_id, credential_ref="cref_tamper0000000001"
    )
    assert envelope is not None
    raw = bytes.fromhex(envelope.ciphertext)
    store.put_credential_envelope(
        envelope.model_copy(update={"ciphertext": (bytes([raw[0] ^ 1]) + raw[1:]).hex()})
    )
    with pytest.raises((InvalidTag, ValueError)):
        vault.get_refresh_token(tenant_id=tenant_id, credential_ref="cref_tamper0000000001")


def test_nonce_tamper_fails_authentication() -> None:
    vault, store, tenant_id = _vault()
    vault.put_refresh_token(
        tenant_id=tenant_id, credential_ref="cref_nonce00000000001", refresh_token="rt-secret"
    )
    envelope = store.get_credential_envelope(
        tenant_id=tenant_id, credential_ref="cref_nonce00000000001"
    )
    assert envelope is not None
    nonce = bytes.fromhex(envelope.nonce)
    store.put_credential_envelope(
        envelope.model_copy(update={"nonce": (bytes([nonce[0] ^ 1]) + nonce[1:]).hex()})
    )
    with pytest.raises((InvalidTag, ValueError)):
        vault.get_refresh_token(tenant_id=tenant_id, credential_ref="cref_nonce00000000001")


def test_wrapped_dek_tamper_fails() -> None:
    vault, store, tenant_id = _vault()
    vault.put_refresh_token(
        tenant_id=tenant_id, credential_ref="cref_dekx000000000001", refresh_token="rt-secret"
    )
    envelope = store.get_credential_envelope(
        tenant_id=tenant_id, credential_ref="cref_dekx000000000001"
    )
    assert envelope is not None
    wrapped = bytes.fromhex(envelope.wrapped_dek)
    store.put_credential_envelope(
        envelope.model_copy(update={"wrapped_dek": (bytes([wrapped[0] ^ 1]) + wrapped[1:]).hex()})
    )
    with pytest.raises((InvalidTag, ValueError)):
        vault.get_refresh_token(tenant_id=tenant_id, credential_ref="cref_dekx000000000001")


def test_wrong_kms_key_fails() -> None:
    repo = InMemoryControlPlaneRepository()
    tenant, _identity = seed_tenant(repo)
    ControlPlaneCredentialVault(repo=repo, kms=FakeKmsKek(kek=b"a" * 32)).put_refresh_token(
        tenant_id=tenant.tenant_id,
        credential_ref="cref_wrong00000000001",
        refresh_token="rt-secret",
    )
    other = ControlPlaneCredentialVault(
        repo=repo,
        kms=FakeKmsKek(
            key_resource=(
                "projects/test/locations/us-central1/keyRings/prem3/cryptoKeys/other"
            ),
            kek=b"b" * 32,
        ),
    )
    with pytest.raises(ValueError):
        other.get_refresh_token(
            tenant_id=tenant.tenant_id, credential_ref="cref_wrong00000000001"
        )


def test_refresh_token_never_plaintext_firestore() -> None:
    harness = google_harness(use_production_vault=True)
    connection_id = connect_google(
        harness, capabilities=["GOOGLE_DRIVE"], refresh_token="rt-secret"
    )
    connection = harness["repo"].get_google_connection(
        tenant_id=harness["tenant"].tenant_id, connection_id=connection_id
    )
    assert connection is not None
    persisted = harness["repo"].get_credential_envelope(
        tenant_id=harness["tenant"].tenant_id, credential_ref=connection.credential_ref
    )
    assert persisted is not None
    dumped = persisted.model_dump()
    assert "rt-secret" not in str(dumped)
    assert persisted.ciphertext != "rt-secret"
    assert persisted.algorithm == PRODUCTION_VAULT_ALGORITHM
    assert "refresh_token" not in dumped


def test_refresh_token_never_public_api() -> None:
    harness = google_harness(use_production_vault=True)
    connect_google(harness, capabilities=["GOOGLE_DRIVE"], refresh_token="rt-secret")
    listed = harness["client"].get("/v1/integrations/google/connections", headers=auth_header())
    assert "rt-secret" not in listed.text
    assert "refresh_token" not in listed.text


def test_refresh_token_never_logged(caplog) -> None:
    harness = google_harness(use_production_vault=True)
    with caplog.at_level(logging.INFO):
        connect_google(harness, capabilities=["GOOGLE_DRIVE"], refresh_token="rt-secret")
    assert "rt-secret" not in caplog.text


def test_missing_incremental_refresh_token_preserves_existing_envelope() -> None:
    harness = google_harness(use_production_vault=True)
    connection_id = connect_google(
        harness, capabilities=["GOOGLE_DRIVE"], refresh_token="rt-keep"
    )
    connection = harness["repo"].get_google_connection(
        tenant_id=harness["tenant"].tenant_id, connection_id=connection_id
    )
    assert connection is not None
    before = harness["repo"].get_credential_envelope(
        tenant_id=harness["tenant"].tenant_id, credential_ref=connection.credential_ref
    )
    started = harness["client"].post(
        "/v1/integrations/google/oauth/start",
        headers=auth_header(),
        json={"capabilities": ["BIGQUERY_READ"], "return_path": "/app/settings"},
    )
    state = parse_qs(urlparse(started.json()["authorization_url"]).query)["state"][0]
    harness["oauth"].seed_code(
        "nort",
        GoogleTokenSet(
            access_token="ya29.user-access",
            refresh_token=None,
            granted_scopes=(
                *OPENID_SCOPES,
                "https://www.googleapis.com/auth/bigquery.readonly",
            ),
            google_subject="google-sub-1",
            display_email="user@example.com",
        ),
    )
    harness["client"].get(
        "/v1/integrations/google/oauth/callback",
        params={"state": state, "code": "nort"},
        follow_redirects=False,
    )
    after = harness["repo"].get_credential_envelope(
        tenant_id=harness["tenant"].tenant_id, credential_ref=connection.credential_ref
    )
    assert before is not None and after is not None
    assert after.ciphertext == before.ciphertext
    assert after.nonce == before.nonce
    assert after.wrapped_dek == before.wrapped_dek
    assert (
        harness["vault"].get_refresh_token(
            tenant_id=harness["tenant"].tenant_id, credential_ref=connection.credential_ref
        )
        == "rt-keep"
    )


def test_disconnect_deletes_credential_envelope() -> None:
    harness = google_harness(use_production_vault=True)
    connection_id = connect_google(
        harness, capabilities=["GOOGLE_DRIVE"], refresh_token="rt-secret"
    )
    connection = harness["repo"].get_google_connection(
        tenant_id=harness["tenant"].tenant_id, connection_id=connection_id
    )
    assert connection is not None
    response = harness["client"].post(
        f"/v1/integrations/google/connections/{connection_id}/disconnect",
        headers=auth_header(),
    )
    assert response.status_code == 200, response.text
    assert (
        harness["repo"].get_credential_envelope(
            tenant_id=harness["tenant"].tenant_id, credential_ref=connection.credential_ref
        )
        is None
    )


def test_live_google_oauth_without_kms_fails_closed() -> None:
    settings = replace(
        load_settings(),
        google_oauth_client_id="client.apps.googleusercontent.com",
        google_oauth_client_secret="secret",
        google_kms_key=None,
    )
    with pytest.raises(RuntimeError, match="GOOGLE_KMS_KEY"):
        _default_google_services(
            settings,
            InMemoryControlPlaneRepository(),
            oauth_provider=object(),
            vault=None,
            drive_client=None,
            bigquery_client=None,
        )


def test_in_memory_vault_remains_local_only() -> None:
    assert InMemoryCredentialVault().envelope(
        tenant_id="t", credential_ref="c"
    ) is None
    assert CloudKmsKek.__name__ == "CloudKmsKek"


def test_credential_envelope_type_has_nonce_and_no_plaintext() -> None:
    fields = CredentialEnvelope.model_fields
    assert "refresh_token" not in fields
    assert "nonce" in fields
    assert "wrapped_dek" in fields
    assert "kms_key" in fields
