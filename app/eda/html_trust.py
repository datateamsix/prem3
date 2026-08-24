"""Inspect Meridian HTML before embed. Provenance, not scraping, owns trust."""

from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import urlparse

from app.eda.extended_contracts import (
    CUSTOMER_UPLOAD_HTML,
    TRUSTED_GENERATED_MERIDIAN_HTML,
    FrozenModel,
)

SCRIPT_RE = re.compile(r"<\s*script\b", re.IGNORECASE)
SCRIPT_SRC_RE = re.compile(
    r"<\s*script[^>]*\bsrc\s*=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
EVENT_HANDLER_RE = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
JAVASCRIPT_URI_RE = re.compile(r"javascript\s*:", re.IGNORECASE)
EXTERNAL_SRC_RE = re.compile(
    r"""(?:src|href|action)\s*=\s*['"]\s*https?://""",
    re.IGNORECASE,
)
FRAME_RE = re.compile(r"<\s*(iframe|object|embed)\b", re.IGNORECASE)

ALLOWED_SCRIPT_ORIGINS = frozenset({"https://www.gstatic.com"})
ALLOWED_STYLE_ORIGINS = frozenset({"https://fonts.googleapis.com"})
ALLOWED_FONT_ORIGINS = frozenset({"https://fonts.gstatic.com"})
ALLOWED_IMG_ORIGINS = frozenset({"https://www.gstatic.com"})
FIXTURE_HTML_REF = "prem3-fixture://meridian_eda_report.html"


class HtmlTrustReport(FrozenModel):
    artifact_class: str
    sha256: str
    has_scripts: bool
    has_inline_js: bool
    has_external_resources: bool
    has_embedded_frames: bool
    embed_allowed: bool
    csp: str
    sandbox: str
    notes: tuple[str, ...] = ()


class HtmlNotTrustedError(ValueError):
    """Official HTML serving refused this payload."""


class HtmlBindingError(ValueError):
    """official_html_ref does not identify the provided bytes."""


def html_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _origin(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def inspect_generated_html(
    payload: bytes,
    *,
    artifact_class: str,
) -> HtmlTrustReport:
    text = payload.decode("utf-8", errors="replace")
    script_srcs = tuple(SCRIPT_SRC_RE.findall(text))
    has_scripts = bool(SCRIPT_RE.search(text))
    has_inline_js = bool(EVENT_HANDLER_RE.search(text) or JAVASCRIPT_URI_RE.search(text))
    has_external = bool(EXTERNAL_SRC_RE.search(text))
    has_frames = bool(FRAME_RE.search(text))
    trusted = artifact_class == TRUSTED_GENERATED_MERIDIAN_HTML
    notes: list[str] = []
    if not trusted:
        notes.append("Arbitrary uploaded HTML cannot use the trusted Meridian embed path.")
    if has_scripts:
        notes.append("Official Meridian charts require isolated script execution.")
    if has_external:
        notes.append(
            "External hosts are allowlisted from the artifact; unknown hosts stay blocked."
        )
    csp, sandbox = _embed_policy(
        trusted=trusted,
        has_scripts=has_scripts,
        text=text,
        script_srcs=script_srcs,
    )
    return HtmlTrustReport(
        artifact_class=artifact_class,
        sha256=html_sha256(payload),
        has_scripts=has_scripts,
        has_inline_js=has_inline_js,
        has_external_resources=has_external,
        has_embedded_frames=has_frames,
        embed_allowed=trusted,
        csp=csp,
        sandbox=sandbox,
        notes=tuple(notes),
    )


def _embed_policy(
    *,
    trusted: bool,
    has_scripts: bool,
    text: str,
    script_srcs: tuple[str, ...],
) -> tuple[str, str]:
    if not trusted:
        return (
            "sandbox; default-src 'none'; script-src 'none'; style-src 'none'; "
            "img-src 'none'; font-src 'none'; connect-src 'none'; frame-src 'none'; "
            "worker-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; "
            "frame-ancestors 'none'",
            "",
        )
    script_src = ["'none'"]
    sandbox = ""
    csp_sandbox = "sandbox"
    if has_scripts:
        sandbox = "allow-scripts"
        csp_sandbox = "sandbox allow-scripts"
        script_src = ["'unsafe-inline'"]
        seen_script_origins: list[str] = []
        for src in script_srcs:
            origin = _origin(src)
            if origin in ALLOWED_SCRIPT_ORIGINS and origin not in seen_script_origins:
                seen_script_origins.append(origin)
        script_src.extend(seen_script_origins)
    style_src = ["'unsafe-inline'"]
    if "fonts.googleapis.com" in text:
        style_src.extend(sorted(ALLOWED_STYLE_ORIGINS))
    font_src = ["'none'"]
    if "fonts.googleapis.com" in text or "fonts.gstatic.com" in text:
        font_src = sorted(ALLOWED_FONT_ORIGINS)
    img_src = ["data:", "blob:"]
    if "www.gstatic.com" in text:
        img_src.extend(sorted(ALLOWED_IMG_ORIGINS))
    csp = (
        f"{csp_sandbox}; default-src 'none'; script-src {' '.join(script_src)}; "
        f"style-src {' '.join(style_src)}; font-src {' '.join(font_src)}; "
        f"img-src {' '.join(img_src)}; connect-src 'none'; frame-src 'none'; "
        "worker-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; "
        "frame-ancestors 'self'"
    )
    return csp, sandbox


def embed_headers(inspection: HtmlTrustReport) -> dict[str, str]:
    return {
        "Content-Security-Policy": inspection.csp,
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",
        "Referrer-Policy": "no-referrer",
        "Cache-Control": "private, no-store",
    }


def require_trusted_meridian_html(
    payload: bytes,
    *,
    artifact_class: str,
    expected_sha256: str,
) -> HtmlTrustReport:
    report = inspect_generated_html(payload, artifact_class=artifact_class)
    if artifact_class != TRUSTED_GENERATED_MERIDIAN_HTML:
        raise HtmlNotTrustedError("Trusted Meridian HTML route rejects non-generated HTML.")
    if artifact_class == CUSTOMER_UPLOAD_HTML:
        raise HtmlNotTrustedError("Customer HTML cannot use TRUSTED_GENERATED_MERIDIAN_HTML.")
    if report.sha256 != expected_sha256:
        raise HtmlNotTrustedError("Official HTML SHA-256 does not match the stored fingerprint.")
    if not report.embed_allowed:
        raise HtmlNotTrustedError("HTML is not classified as TRUSTED_GENERATED_MERIDIAN_HTML.")
    return report


def assert_html_binding(
    *,
    official_html_ref: str,
    payload: bytes,
    expected_sha256: str | None = None,
    fixture_sha256: str | None = None,
    known_live_sha256: dict[str, str] | None = None,
) -> str:
    digest = html_sha256(payload)
    if expected_sha256 is not None and expected_sha256 != digest:
        raise HtmlBindingError(
            "URI/hash mismatch: official_html_sha256 does not match provided bytes."
        )
    if official_html_ref == FIXTURE_HTML_REF and fixture_sha256 is not None:
        if digest != fixture_sha256:
            raise HtmlBindingError("Fixture ref does not match local fixture bytes.")
    if fixture_sha256 is not None and official_html_ref.startswith("gs://"):
        if digest == fixture_sha256:
            raise HtmlBindingError(
                "Live official_html_ref cannot bind local fixture bytes."
            )
    pinned = (known_live_sha256 or {}).get(official_html_ref)
    if pinned is not None and pinned != digest:
        raise HtmlBindingError(
            "URI/hash mismatch: live official_html_ref does not match artifact bytes."
        )
    return digest


def trust_report_payload(report: HtmlTrustReport) -> dict[str, Any]:
    return report.model_dump(mode="json")
