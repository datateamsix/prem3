"""Encrypted Google credential vault. Refresh tokens never stored plaintext."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from google.cloud import kms_v1

from app.control_plane.models import CredentialEnvelope
from app.control_plane.repository import ControlPlaneRepository

PRODUCTION_VAULT_ALGORITHM = "aes-256-gcm+kms-v1"
TEST_VAULT_ALGORITHM = "aes-256-gcm-test-v1"
_DEK_SIZE = 32
_NONCE_SIZE = 12


class CredentialVault(Protocol):
    def put_refresh_token(
        self, *, tenant_id: str, credential_ref: str, refresh_token: str
    ) -> CredentialEnvelope: ...

    def get_refresh_token(self, *, tenant_id: str, credential_ref: str) -> str | None: ...

    def delete(self, *, tenant_id: str, credential_ref: str) -> None: ...


class KmsKek(Protocol):
    key_resource: str

    def encrypt(self, plaintext: bytes) -> bytes: ...

    def decrypt(self, ciphertext: bytes) -> bytes: ...


class FakeKmsKek:
    """Local/CI KEK. Not a production Cloud KMS substitute."""

    def __init__(
        self,
        *,
        key_resource: str = (
            "projects/test/locations/us-central1/keyRings/prem3/cryptoKeys/"
            "prem3-google-oauth-credentials"
        ),
        kek: bytes | None = None,
    ) -> None:
        self.key_resource = key_resource
        material = kek if kek is not None else b"prem3-test-kms-kek-material-32b!"
        self._aes = AESGCM(material)

    def encrypt(self, plaintext: bytes) -> bytes:
        nonce = os.urandom(_NONCE_SIZE)
        return nonce + self._aes.encrypt(nonce, plaintext, None)

    def decrypt(self, ciphertext: bytes) -> bytes:
        if len(ciphertext) <= _NONCE_SIZE:
            raise ValueError("Wrapped DEK is truncated.")
        return self._aes.decrypt(ciphertext[:_NONCE_SIZE], ciphertext[_NONCE_SIZE:], None)


class CloudKmsKek:
    """Symmetric Cloud KMS encrypt/decrypt of the per-credential DEK."""

    def __init__(self, key_resource: str, *, client=None) -> None:
        if not key_resource:
            raise RuntimeError("GOOGLE_KMS_KEY is required for production Google credentials.")
        self.key_resource = key_resource
        self._client = client or kms_v1.KeyManagementServiceClient()

    def encrypt(self, plaintext: bytes) -> bytes:
        response = self._client.encrypt(request={"name": self.key_resource, "plaintext": plaintext})
        return bytes(response.ciphertext)

    def decrypt(self, ciphertext: bytes) -> bytes:
        response = self._client.decrypt(
            request={"name": self.key_resource, "ciphertext": ciphertext}
        )
        return bytes(response.plaintext)


def _aad(*, tenant_id: str, credential_ref: str) -> bytes:
    return f"{tenant_id}:{credential_ref}".encode()


def _seal(
    *,
    dek: bytes,
    nonce: bytes,
    plaintext: bytes,
    tenant_id: str,
    credential_ref: str,
) -> bytes:
    return AESGCM(dek).encrypt(
        nonce, plaintext, _aad(tenant_id=tenant_id, credential_ref=credential_ref)
    )


def _open(
    *,
    dek: bytes,
    nonce: bytes,
    ciphertext: bytes,
    tenant_id: str,
    credential_ref: str,
) -> bytes:
    return AESGCM(dek).decrypt(
        nonce, ciphertext, _aad(tenant_id=tenant_id, credential_ref=credential_ref)
    )


class InMemoryCredentialVault:
    """Local/CI vault. AES-GCM in process; never stores plaintext refresh tokens."""

    def __init__(self, *, master_key: bytes | None = None) -> None:
        del master_key
        self._kms = FakeKmsKek()
        self._envelopes: dict[tuple[str, str], CredentialEnvelope] = {}
        self.plaintexts_written: list[str] = []

    def put_refresh_token(
        self, *, tenant_id: str, credential_ref: str, refresh_token: str
    ) -> CredentialEnvelope:
        envelope = _encrypt_envelope(
            tenant_id=tenant_id,
            credential_ref=credential_ref,
            refresh_token=refresh_token,
            kms=self._kms,
            algorithm=TEST_VAULT_ALGORITHM,
            existing=self._envelopes.get((tenant_id, credential_ref)),
        )
        self._envelopes[(tenant_id, credential_ref)] = envelope
        return envelope

    def get_refresh_token(self, *, tenant_id: str, credential_ref: str) -> str | None:
        envelope = self._envelopes.get((tenant_id, credential_ref))
        if envelope is None:
            return None
        return _decrypt_envelope(envelope, kms=self._kms)

    def delete(self, *, tenant_id: str, credential_ref: str) -> None:
        self._envelopes.pop((tenant_id, credential_ref), None)

    def envelope(self, *, tenant_id: str, credential_ref: str) -> CredentialEnvelope | None:
        return self._envelopes.get((tenant_id, credential_ref))


class ControlPlaneCredentialVault:
    """Persists AES-256-GCM ciphertext and a KMS-wrapped DEK. Never plaintext."""

    def __init__(self, *, repo: ControlPlaneRepository, kms: KmsKek) -> None:
        if not getattr(kms, "key_resource", ""):
            raise RuntimeError("Production credential vault requires a KMS key resource.")
        self._repo = repo
        self._kms = kms

    def put_refresh_token(
        self, *, tenant_id: str, credential_ref: str, refresh_token: str
    ) -> CredentialEnvelope:
        existing = self._repo.get_credential_envelope(
            tenant_id=tenant_id, credential_ref=credential_ref
        )
        envelope = _encrypt_envelope(
            tenant_id=tenant_id,
            credential_ref=credential_ref,
            refresh_token=refresh_token,
            kms=self._kms,
            algorithm=PRODUCTION_VAULT_ALGORITHM,
            existing=existing,
        )
        return self._repo.put_credential_envelope(envelope)

    def get_refresh_token(self, *, tenant_id: str, credential_ref: str) -> str | None:
        envelope = self._repo.get_credential_envelope(
            tenant_id=tenant_id, credential_ref=credential_ref
        )
        if envelope is None:
            return None
        if envelope.algorithm != PRODUCTION_VAULT_ALGORITHM:
            raise ValueError("Unsupported credential envelope algorithm.")
        return _decrypt_envelope(envelope, kms=self._kms)

    def delete(self, *, tenant_id: str, credential_ref: str) -> None:
        self._repo.delete_credential_envelope(tenant_id=tenant_id, credential_ref=credential_ref)

    def envelope(self, *, tenant_id: str, credential_ref: str) -> CredentialEnvelope | None:
        return self._repo.get_credential_envelope(
            tenant_id=tenant_id, credential_ref=credential_ref
        )


def _encrypt_envelope(
    *,
    tenant_id: str,
    credential_ref: str,
    refresh_token: str,
    kms: KmsKek,
    algorithm: str,
    existing: CredentialEnvelope | None,
) -> CredentialEnvelope:
    if not refresh_token:
        raise ValueError("refresh_token must not be empty.")
    dek = os.urandom(_DEK_SIZE)
    nonce = os.urandom(_NONCE_SIZE)
    token_bytes = refresh_token.encode()
    ciphertext = _seal(
        dek=dek,
        nonce=nonce,
        plaintext=token_bytes,
        tenant_id=tenant_id,
        credential_ref=credential_ref,
    )
    wrapped = kms.encrypt(dek)
    token_bytes = b"\x00" * len(token_bytes)
    dek = b"\x00" * len(dek)
    del token_bytes, dek
    now = datetime.now(UTC)
    return CredentialEnvelope(
        tenant_id=tenant_id,
        credential_ref=credential_ref,
        algorithm=algorithm,
        ciphertext=ciphertext.hex(),
        nonce=nonce.hex(),
        wrapped_dek=wrapped.hex(),
        kms_key=kms.key_resource,
        created_at=existing.created_at if existing is not None else now,
        updated_at=now,
    )


def _decrypt_envelope(envelope: CredentialEnvelope, *, kms: KmsKek) -> str:
    if envelope.kms_key and envelope.kms_key != kms.key_resource:
        raise ValueError("Credential envelope was wrapped by a different KMS key.")
    dek = kms.decrypt(bytes.fromhex(envelope.wrapped_dek))
    try:
        raw = _open(
            dek=dek,
            nonce=bytes.fromhex(envelope.nonce),
            ciphertext=bytes.fromhex(envelope.ciphertext),
            tenant_id=envelope.tenant_id,
            credential_ref=envelope.credential_ref,
        )
        return raw.decode()
    finally:
        dek = b"\x00" * len(dek)
        del dek
