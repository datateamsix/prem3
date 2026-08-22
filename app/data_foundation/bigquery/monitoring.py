"""Re-run the same quality contracts used at onboarding."""

from __future__ import annotations

from app.data_foundation.context import DataFoundationContext
from app.data_foundation.service import DataFoundationService


def reevaluate(service: DataFoundationService, context: DataFoundationContext, source_id: str):
    return service.reevaluate_health(context, source_id)
