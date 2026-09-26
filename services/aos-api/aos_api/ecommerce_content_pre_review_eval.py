"""No-effect, deterministic content completeness gate for isolated Eval cases.

This draft graph is not a published Eval authority. Production callers must use
the persisted, published graph and an exact READY EvalContract instead.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aos_api.aip_logic_dry_run_executor import LogicDryRunExecutor
from aos_api.aip_logic_graph_models import (
    CreateLogicGraphRequest,
    LogicGraphSnapshot,
    compute_logic_graph_hash,
)


GRAPH_ID = "ecommerce.content.pre-review.v1"
INPUT_SCHEMA_VERSION = "aos.eval-ecommerce-content-input/v1"
_REQUIRED_CONTENT = (
    "body", "productNames", "channels", "sourceArtifactRefs",
    "factSourceRefs", "constraintChecks",
)


def build_content_pre_review_graph() -> CreateLogicGraphRequest:
    """Build a draft, effect-free LogicGraph request; never publish implicitly."""
    return CreateLogicGraphRequest(
        id=GRAPH_ID,
        name="电商内容人工评审前完整性检查",
        description="仅检查产物与来源字段齐全，不判断事实正确或合规通过。",
        nodes=[
            {
                "id": "content_input", "kind": "input", "label": "可读内容输入",
                "config": {"schema": {
                    "type": "object",
                    "required": ["schemaVersion", "subjectArtifactRef", "content"],
                    "properties": {
                        "schemaVersion": {"type": "string"},
                        "subjectArtifactRef": {"type": "object"},
                        "content": {"type": "object"},
                    },
                }},
            },
            {
                "id": "completeness", "kind": "transform", "label": "结构与来源完整性",
                "config": {"expression": (
                    'inputs.schemaVersion == "' + INPUT_SCHEMA_VERSION + '"'
                    ' && len(inputs.content.body) > 0'
                    ' && len(inputs.content.productNames) > 0'
                    ' && len(inputs.content.channels) > 0'
                    ' && len(inputs.content.sourceArtifactRefs) > 0'
                    ' && len(inputs.content.factSourceRefs) > 0'
                    ' && len(inputs.content.constraintChecks) > 0'
                )},
            },
        ],
        edges=[{"id": "input_to_completeness", "source_node_id": "content_input",
                "target_node_id": "completeness"}],
        entry_node_ids=["content_input"],
    )


def evaluate_content_pre_review(graph: CreateLogicGraphRequest, payload: dict[str, Any]) -> bool:
    """Evaluate an isolated fixture; false means no authority to enter review."""
    canonical = build_content_pre_review_graph()
    if graph != canonical or not isinstance(payload, dict):
        return False
    content = payload.get("content")
    artifact = payload.get("subjectArtifactRef")
    if not isinstance(content, dict) or not isinstance(artifact, dict):
        return False
    if artifact.get("resourceType") != "Artifact" or not all(
        isinstance(artifact.get(key), str) and artifact[key].strip()
        for key in ("resourceId", "contentHash")
    ):
        return False
    if not isinstance(content.get("body"), str) or not content["body"].strip():
        return False
    if any(not isinstance(content.get(key), list) or not content[key]
           for key in _REQUIRED_CONTENT if key != "body"):
        return False
    now = datetime.now(UTC)
    snapshot = LogicGraphSnapshot(
        id=graph.id,
        name=graph.name,
        description=graph.description,
        status="draft",
        schema_version=graph.schema_version,
        revision=1,
        graph_hash=compute_logic_graph_hash(graph),
        nodes=graph.nodes,
        edges=graph.edges,
        entry_node_ids=graph.entry_node_ids,
        created_at=now,
        updated_at=now,
        persisted=False,
    )
    try:
        result = LogicDryRunExecutor().execute(snapshot, payload)
    except (ValueError, TypeError):
        return False
    return result.status == "succeeded" and any(
        node.node_id == "completeness" and node.status == "executed" and node.output is True
        for node in result.node_results
    )
