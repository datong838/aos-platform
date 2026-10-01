"""N5 Handoff payload helpers with no token or transport authority."""

from __future__ import annotations

from .ecommerce_business_investigation_review_command import (
    AcceptedStageHandoffRequest,
    ReviewHandoffRequest,
)


def build_review_handoff_command(request: ReviewHandoffRequest) -> dict[str, object]:
    """Build a host command; the package never signs or persists a Handoff."""
    return request.command_payload()


def build_accepted_stage_handoff_command(request: AcceptedStageHandoffRequest) -> dict[str, object]:
    """Build an exact proposal; current Host execution remains closed."""
    if type(request) is not AcceptedStageHandoffRequest:
        raise TypeError("accepted stage Handoff request required")
    return request.command_payload()


__all__ = ["build_review_handoff_command", "build_accepted_stage_handoff_command"]
