"""Google-signed service identity for internal Evaluation launch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.service.errors import service_identity_required

try:
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token
except ImportError:  # pragma: no cover
    google_requests = None
    id_token = None


@dataclass(frozen=True, slots=True)
class ServiceIdentity:
    email: str
    subject: str
    audience: str


class ServiceIdentityVerifier(Protocol):
    def verify(self, authorization: str | None) -> ServiceIdentity: ...


class FakeServiceIdentityVerifier:
    def __init__(self, *, allowed_email: str, audience: str) -> None:
        self.allowed_email = allowed_email
        self.audience = audience
        self.identities: dict[str, ServiceIdentity] = {}

    def verify(self, authorization: str | None) -> ServiceIdentity:
        token = _bearer_token(authorization)
        if token is None:
            raise service_identity_required()
        identity = self.identities.get(token)
        if identity is None:
            raise service_identity_required()
        if identity.email != self.allowed_email or identity.audience != self.audience:
            raise service_identity_required()
        return identity


class GoogleOidcServiceIdentityVerifier:
    def __init__(self, *, allowed_email: str, audience: str) -> None:
        self._allowed_email = allowed_email
        self._audience = audience

    def verify(self, authorization: str | None) -> ServiceIdentity:
        token = _bearer_token(authorization)
        if token is None:
            raise service_identity_required()
        if google_requests is None or id_token is None:
            raise service_identity_required()
        request = google_requests.Request()
        try:
            payload = id_token.verify_oauth2_token(token, request, audience=self._audience)
        except Exception:
            raise service_identity_required() from None
        if not isinstance(payload, dict):
            raise service_identity_required()
        email = str(payload.get("email") or "").strip()
        subject = str(payload.get("sub") or "").strip()
        if email != self._allowed_email or not subject:
            raise service_identity_required()
        if payload.get("email_verified") is False:
            raise service_identity_required()
        issuer = str(payload.get("iss") or "")
        if issuer not in {
            "https://accounts.google.com",
            "accounts.google.com",
        }:
            raise service_identity_required()
        return ServiceIdentity(email=email, subject=subject, audience=self._audience)


def _bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    raw = authorization.strip()
    if not raw.lower().startswith("bearer "):
        return None
    token = raw[7:].strip()
    return token or None

