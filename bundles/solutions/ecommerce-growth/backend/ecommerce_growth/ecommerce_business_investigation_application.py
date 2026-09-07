"""N1 command composition; execution remains fenced until AR2-7 cutover."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from aos_extension_sdk import DispatchRef

from .sdk_ports import GrowthWritePort
from .analysis_runtime import AnalysisRuntimeRequest, AnalysisRuntimeReceipt, advance_analysis_runtime
from .sdk_ports import GrowthRuntimePort
from .ecommerce_business_investigation_review_command import ReviewHandoffRequest
from .ecommerce_content_campaign_workflow import ReviewHandoffReceipt, advance_review_handoff
from .sdk_ports import GrowthReviewPort
from .content_artifact_review import (
    ContentReviewReceipt,
    ContentReviewRequest,
    review_content_artifact,
)
from .content_capability_runtime import (
    ContentCapabilityReceipt,
    ContentCapabilityRequest,
    execute_content_capability,
)
from .sdk_ports import GrowthCapabilityPort, GrowthContentReviewPort


class EcommerceGrowthApplication:
    def __init__(
        self,
        write_port: GrowthWritePort,
        runtime_port: GrowthRuntimePort | None = None,
        review_port: GrowthReviewPort | None = None,
        capability_port: GrowthCapabilityPort | None = None,
        content_review_port: GrowthContentReviewPort | None = None,
    ) -> None:
        self._write_port = write_port
        self._runtime_port = runtime_port
        self._review_port = review_port
        self._capability_port = capability_port
        self._content_review_port = content_review_port

    def commit_case_or_schedule(
        self,
        *,
        dispatch_ref: DispatchRef,
        command: Mapping[str, Any],
        occurred_at: datetime,
    ) -> Mapping[str, Any]:
        if dispatch_ref.operation_id not in {
            "ecommerce_growth_case_put",
            "ecommerce_growth_schedule_put",
        }:
            raise ValueError("dispatch operation does not belong to N1")
        if occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must include timezone")
        if any(key in command for key in ("tenant", "dispatchRef", "installationId", "generation")):
            raise ValueError("command cannot override host authority")
        return self._write_port.commit(
            dispatch_ref=dispatch_ref,
            command=dict(command),
            occurred_at=occurred_at,
        )

    def advance_analysis(
        self,
        *,
        dispatch_ref: DispatchRef,
        request: AnalysisRuntimeRequest,
    ) -> AnalysisRuntimeReceipt:
        if self._runtime_port is None:
            raise RuntimeError("analysis runtime port is not configured")
        return advance_analysis_runtime(
            self._runtime_port,
            dispatch_ref=dispatch_ref,
            request=request,
        )

    def advance_review(
        self,
        *,
        dispatch_ref: DispatchRef,
        request: ReviewHandoffRequest,
    ) -> ReviewHandoffReceipt:
        if self._review_port is None:
            raise RuntimeError("review Handoff port is not configured")
        return advance_review_handoff(
            self._review_port,
            dispatch_ref=dispatch_ref,
            request=request,
        )

    def execute_content(
        self,
        *,
        dispatch_ref: DispatchRef,
        request: ContentCapabilityRequest,
    ) -> ContentCapabilityReceipt:
        if self._capability_port is None:
            raise RuntimeError("content capability port is not configured")
        return execute_content_capability(
            self._capability_port,
            dispatch_ref=dispatch_ref,
            request=request,
        )

    def review_content(
        self,
        *,
        dispatch_ref: DispatchRef,
        request: ContentReviewRequest,
    ) -> ContentReviewReceipt:
        if self._content_review_port is None:
            raise RuntimeError("content review port is not configured")
        return review_content_artifact(
            self._content_review_port,
            dispatch_ref=dispatch_ref,
            request=request,
        )


__all__ = ["EcommerceGrowthApplication"]
