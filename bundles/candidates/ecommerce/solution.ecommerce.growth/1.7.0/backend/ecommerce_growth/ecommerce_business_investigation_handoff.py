"""N5 Handoff payload helpers with no token or transport authority."""

from __future__ import annotations

from .ecommerce_business_investigation_review_command import ReviewHandoffRequest


def build_review_handoff_command(request: ReviewHandoffRequest) -> dict[str, object]:
    """Build a host command; the package never signs or persists a Handoff."""
    return request.command_payload()


__all__ = ["build_review_handoff_command"]
