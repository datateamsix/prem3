"""Private/no-store helpers for amount-bearing Planning responses."""

from __future__ import annotations

from typing import Any

from app.investment_planning.contracts import AMOUNT_BEARING_MODELS, FrozenModel
from app.investment_planning.enums import SensitiveDataClass

PRIVATE_NO_STORE_HEADERS: dict[str, str] = {
    "Cache-Control": "private, no-store",
    "Pragma": "no-cache",
}

SYNTHETIC_TEST_AMOUNTS: tuple[str, ...] = ("123456.78", "987654.32")
REDACTED_AMOUNT = "[REDACTED_AMOUNT]"


def amount_bearing_response_headers() -> dict[str, str]:
    return dict(PRIVATE_NO_STORE_HEADERS)


def is_amount_bearing(value: object) -> bool:
    return isinstance(value, AMOUNT_BEARING_MODELS) or (
        isinstance(value, FrozenModel)
        and getattr(type(value), "sensitive_data_class", None)
        is SensitiveDataClass.CUSTOMER_AMOUNT_TRANSIENT
    )


def redact_customer_amounts(text: str) -> str:
    redacted = text
    for token in SYNTHETIC_TEST_AMOUNTS:
        redacted = redacted.replace(token, REDACTED_AMOUNT)
    return redacted


def safe_log_text(value: Any) -> str:
    return redact_customer_amounts(str(value))
