"""Deterministic Eval-pack specifications for the no-effect content gate.

Building these specs has no database or publication side effect. A governance
suite releases the Graph; a separate one-case suite evaluates each exact
content Artifact. Neither suite decides factuality or legal compliance.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from typing import Any

from aos_api.aip_contracts import ArtifactRef
from aos_api.aip_eval_contracts import (
    AssetRevisionRef, AssetType, DatasetPiiState, DatasetRevisionRef,
    DatasetSourceKind, EvalCaseDefinition, EvalCaseKind, EvalDatasetManifest,
    EvalSuiteRevision, JudgeRevisionRef,
)
from aos_api.aip_eval_pack_registry import compute_eval_suite_hash
from aos_api.aip_logic_graph_models import compute_logic_graph_hash
from aos_api.ecommerce_content_pre_review_eval import (
    GRAPH_ID, INPUT_SCHEMA_VERSION, build_content_pre_review_graph,
)


def _hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ContentPreReviewEvalPack:
    dataset: DatasetRevisionRef
    manifest: EvalDatasetManifest
    suite: EvalSuiteRevision
    artifacts: dict[tuple[str, str], Any]

    def expected_values(self) -> dict[str, bool]:
        return {
            case.case_id: self.artifacts[
                (case.expected_artifact.artifact_id, case.expected_artifact.revision)
            ]
            for case in self.suite.cases if case.expected_artifact is not None
        }


def _sample() -> dict[str, Any]:
    return {
        "schemaVersion": INPUT_SCHEMA_VERSION,
        "subjectArtifactRef": {
            "resourceType": "Artifact", "resourceId": "isolated-governance-artifact",
            "contentHash": "a" * 64,
        },
        "content": {
            "body": "隔离评测正文；事实仍待人工核实。",
            "productNames": ["隔离评测商品"], "channels": ["内部评测"],
            "sourceArtifactRefs": [{"resourceType": "ArtifactRevision",
                                    "resourceId": "isolated-source", "revision": 1,
                                    "contentHash": "sha256:" + "b" * 64}],
            "factSourceRefs": [{"resourceType": "EvidenceBundleRevision",
                                "resourceId": "isolated-fact", "revision": 1,
                                "contentHash": "sha256:" + "c" * 64}],
            "constraintChecks": ["待人工核对"],
        },
        "caseInput": {"purpose": "isolated-contract-governance"},
    }


def _build_pack(target: AssetRevisionRef, suffix: str,
                cases: list[tuple[str, EvalCaseKind, dict[str, Any], bool]]) -> ContentPreReviewEvalPack:
    suite_id = f"ecommerce.content.pre-review.{suffix}.v1"
    artifacts: dict[tuple[str, str], Any] = {}
    definitions: list[EvalCaseDefinition] = []
    for case_id, kind, input_value, expected_value in cases:
        input_ref = ArtifactRef(
            artifact_id=f"{suite_id}.{case_id}.input", artifact_type="eval_input",
            revision="1", content_hash=_hash(input_value),
        )
        expected_ref = ArtifactRef(
            artifact_id=f"{suite_id}.{case_id}.expected", artifact_type="eval_expected",
            revision="1", content_hash=_hash(expected_value),
        )
        artifacts[(input_ref.artifact_id, "1")] = input_value
        artifacts[(expected_ref.artifact_id, "1")] = expected_value
        definitions.append(EvalCaseDefinition(
            case_id=case_id, kind=kind, input_artifact=input_ref,
            expected_artifact=expected_ref, timeout_ms=1_000,
        ))
    source_hash = _hash({"suiteId": suite_id, "targetHash": target.content_hash,
                         "caseIds": [item.case_id for item in definitions]})
    dataset_id = f"{suite_id}.dataset"
    dataset = DatasetRevisionRef(
        dataset_id=dataset_id, revision=1,
        content_hash=_hash({"datasetId": dataset_id, "sourceHash": source_hash}),
        source_hash=source_hash,
        redaction_policy=AssetRevisionRef(
            asset_type=AssetType.POLICY,
            asset_id="ecommerce-content-pre-review-no-pii-policy",
            revision="1", content_hash=_hash("no-pii-governance-v1"),
        ),
    )
    manifest = EvalDatasetManifest(
        source_kind=DatasetSourceKind.ARTIFACT_SNAPSHOT,
        source_id=f"ecommerce-content-pre-review-{suffix}-cases",
        source_revision="1", source_hash=source_hash,
        fields_allowlist=["schemaVersion", "subjectArtifactRef", "content", "caseInput"],
        redaction_receipt=ArtifactRef(
            artifact_id=f"{suite_id}.redaction", artifact_type="redaction_receipt",
            revision="1", content_hash=_hash("no-personal-data-v1"),
        ),
        pii_state=DatasetPiiState.NONE, case_count=len(definitions),
        captured_at=datetime(2026, 9, 26, tzinfo=UTC),
    )
    judge = JudgeRevisionRef(
        judge_id="ecommerce-content-pre-review-exact-bool-judge",
        revision=1, content_hash=_hash("exact-bool-judge-v1"),
    )
    suite = EvalSuiteRevision(
        suite_id=suite_id, revision=1, content_hash="0" * 64,
        target=target, dataset=dataset, judge=judge,
        cases=definitions, gate_threshold=1.0,
    )
    suite = suite.model_copy(update={"content_hash": compute_eval_suite_hash(suite)})
    return ContentPreReviewEvalPack(dataset, manifest, suite, artifacts)


def build_content_pre_review_eval_packs(
    target: AssetRevisionRef,
) -> tuple[ContentPreReviewEvalPack, ContentPreReviewEvalPack]:
    """Return immutable refs plus local case values; never register implicitly."""
    if (
        target.asset_type is not AssetType.LOGIC_GRAPH
        or target.asset_id != GRAPH_ID
        or target.content_hash != compute_logic_graph_hash(build_content_pre_review_graph())
    ):
        raise ValueError("content pre-review packs require the exact LogicGraph identity")
    positive = _sample()
    blank = deepcopy(positive)
    blank["content"]["body"] = ""
    missing_fact = deepcopy(positive)
    missing_fact["content"]["factSourceRefs"] = []
    missing_channel = deepcopy(positive)
    missing_channel["content"]["channels"] = []
    wrong_schema = deepcopy(positive)
    wrong_schema["schemaVersion"] = "wrong"
    governance = _build_pack(target, "governance", [
        ("complete", EvalCaseKind.POSITIVE, positive, True),
        ("blank-body", EvalCaseKind.NEGATIVE, blank, False),
        ("missing-fact", EvalCaseKind.BOUNDARY, missing_fact, False),
        ("missing-channel", EvalCaseKind.BOUNDARY, missing_channel, False),
        ("wrong-schema", EvalCaseKind.NEGATIVE, wrong_schema, False),
    ])
    subject = _build_pack(target, "subject", [
        ("content-subject", EvalCaseKind.POSITIVE,
         {"caseId": "content-subject"}, True),
    ])
    return governance, subject
