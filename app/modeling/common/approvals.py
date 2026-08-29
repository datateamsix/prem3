"""Human approval records. Approvals bind to fingerprints, never to chat."""

from app.modeling.mmm.contracts import FitApproval, ModelAcceptanceApproval

__all__ = ["FitApproval", "ModelAcceptanceApproval"]
