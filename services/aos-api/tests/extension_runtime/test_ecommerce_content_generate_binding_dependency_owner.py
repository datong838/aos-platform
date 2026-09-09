from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from aos_api.aip_agent_registry_contracts import OperationalBindingDependencies, VersionedAssetRef
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_production_contract_store import canonical_hash
from aos_api.db import connect
from aos_api.ecommerce_growth_runtime_adapters import ContentGenerateHostService
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 9, 9, 10, tzinfo=UTC)


def ref(kind, identity, digest):
    return VersionedAssetRef(
        assetType=kind, assetId=identity, revision=1, contentHash=digest
    )


class Transaction:
    def __init__(self):
        self.eval_content = {
            "suiteRef": {"resourceType": "EvalSuiteRevision", "resourceId": "suite-1", "revision": 1, "contentHash": "a" * 64},
            "publicationRef": None,
            "releaseGateRef": None,
            "artifactSchemaRef": {"resourceType": "SchemaRevision", "resourceId": "schema-1", "revision": 1, "contentHash": "b" * 64},
            "severityThresholds": {}, "gatePolicy": {}, "returnMapping": {}, "overridePolicy": {},
        }
        self.eval_ref = ref("EvalContractRevision", "eval-1", canonical_hash(self.eval_content))
        self.data_ref = ref("EvalDatasetRevision", "data-1", "2" * 64)
        self.tool_ref = ref("EvidenceBundleRevision", "tool-1", "3" * 64)
        self.license = ResourceRef(
            resourceType="EvidenceBundleRevision",
            resourceId="license-1",
            revision="1",
            authority="aip-production-contract",
        )
        self.dependencies = OperationalBindingDependencies(
            evalContractRef=self.eval_ref,
            licenseEvidenceRefs=[self.license],
            dataDependencyRefs=[self.data_ref],
            toolDependencyRefs=[self.tool_ref],
        )
        self.dependency_row = {
            "license_evidence_refs": [
                self.license.model_dump(mode="json", by_alias=True, exclude_none=True)
            ]
        }
        self.capability = SimpleNamespace(
            required_data_refs=[self.data_ref], required_tool_refs=[self.tool_ref]
        )
        self.eval_row = {
            "current_revision": 1,
            "version": 1,
            "content_hash": self.eval_ref.content_hash,
            "lifecycle": "frozen",
            "created_at": NOW - timedelta(days=1),
            "suite_ref": self.eval_content["suiteRef"],
            "publication_ref": None,
            "release_gate_ref": None,
            "artifact_schema_ref": self.eval_content["artifactSchemaRef"],
            "severity_thresholds": {},
            "gate_policy": {},
            "return_mapping": {},
            "override_policy": {},
        }
        self.license_row = {
            "lifecycle": "frozen",
            "license_summary": {"license": "internal"},
            "content_hash": "c" * 64,
            "created_at": NOW - timedelta(days=1),
        }
        self.data_row = {
            "content_hash": self.data_ref.content_hash,
            "created_at": NOW - timedelta(days=1),
        }
        self.tool_row = {
            "content_hash": self.tool_ref.content_hash,
            "lifecycle": "frozen",
            "created_at": NOW - timedelta(days=1),
        }
        self.revoked_ids = set()

    def execute(self, query, params=()):
        if "aip_eval_contract_head" in query:
            value = self.eval_row
        elif "aip_eval_dataset_revision" in query:
            value = self.data_row
        elif "aip_evidence_bundle_revoke_event" in query:
            value = {"event_id": "revoke-1"} if params[-4] in self.revoked_ids else None
        elif "aip_evidence_bundle_revision" in query:
            value = self.license_row if params[-2] == "license-1" else self.tool_row
        else:
            raise AssertionError(query)

        class Result:
            def fetchone(inner):
                return value

        return Result()


def validate(transaction):
    ContentGenerateHostService._binding_dependency_authority(
        transaction,
        SCOPE,
        transaction.capability,
        transaction.dependencies,
        transaction.dependency_row,
        checked_at=NOW,
    )


def test_binding_dependencies_accept_exact_current_owners():
    validate(Transaction())


def test_eval_contract_query_matches_migrated_postgres_schema():
    transaction = Transaction()
    transaction.eval_ref = ref("EvalContractRevision", "missing-eval", "1" * 64)
    transaction.dependencies = transaction.dependencies.model_copy(
        update={"eval_contract_ref": transaction.eval_ref}
    )
    with connect(SCOPE) as connection:
        with pytest.raises(ValueError, match="EvalContract dependency drifted"):
            validate_with_connection(transaction, connection)


def validate_with_connection(transaction, connection):
    ContentGenerateHostService._binding_dependency_authority(
        connection, SCOPE, transaction.capability, transaction.dependencies,
        transaction.dependency_row, checked_at=NOW,
    )


@pytest.mark.parametrize(
    "drift",
    (
        "eval_missing", "eval_head_bool", "eval_old", "eval_hash", "eval_lifecycle",
        "eval_future", "eval_body", "license_empty", "license_duplicate", "license_revision_bool",
        "license_revision_noncanonical", "license_whitespace", "license_type",
        "license_missing", "license_lifecycle", "license_summary", "license_future", "license_revoked",
        "data_uncovered", "tool_uncovered", "data_unknown", "data_missing",
        "data_hash", "data_future", "tool_lifecycle", "tool_revoked",
    ),
)
def test_binding_dependencies_reject_owner_drift(drift):
    transaction = Transaction()
    if drift == "eval_missing": transaction.eval_row = None
    elif drift == "eval_head_bool": transaction.eval_row["version"] = True
    elif drift == "eval_old": transaction.eval_row["current_revision"] = 2
    elif drift == "eval_hash": transaction.eval_row["content_hash"] = "f" * 64
    elif drift == "eval_lifecycle": transaction.eval_row["lifecycle"] = "withdrawn"
    elif drift == "eval_future": transaction.eval_row["created_at"] = NOW + timedelta(seconds=1)
    elif drift == "eval_body": transaction.eval_row["gate_policy"] = {"changed": True}
    elif drift == "license_empty": transaction.dependency_row["license_evidence_refs"] = []
    elif drift == "license_duplicate": transaction.dependency_row["license_evidence_refs"].append(deepcopy(transaction.dependency_row["license_evidence_refs"][0]))
    elif drift == "license_revision_bool": transaction.dependency_row["license_evidence_refs"][0]["revision"] = True
    elif drift == "license_revision_noncanonical": transaction.dependency_row["license_evidence_refs"][0]["revision"] = "01"
    elif drift == "license_whitespace": transaction.dependency_row["license_evidence_refs"][0]["resourceId"] = " license-1 "
    elif drift == "license_type": transaction.dependency_row["license_evidence_refs"][0]["resourceType"] = "Other"
    elif drift == "license_missing": transaction.license_row = None
    elif drift == "license_lifecycle": transaction.license_row["lifecycle"] = "withdrawn"
    elif drift == "license_summary": transaction.license_row["license_summary"] = {}
    elif drift == "license_future": transaction.license_row["created_at"] = NOW + timedelta(seconds=1)
    elif drift == "license_revoked": transaction.revoked_ids.add("license-1")
    elif drift == "data_uncovered": transaction.capability.required_data_refs = [ref("EvalDatasetRevision", "other", "2" * 64)]
    elif drift == "tool_uncovered": transaction.capability.required_tool_refs = [ref("EvidenceBundleRevision", "other", "3" * 64)]
    elif drift == "data_unknown": transaction.dependencies = transaction.dependencies.model_copy(update={"data_dependency_refs": [ref("UnknownRevision", "data-1", "2" * 64)]})
    elif drift == "data_missing": transaction.data_row = None
    elif drift == "data_hash": transaction.data_row["content_hash"] = "f" * 64
    elif drift == "data_future": transaction.data_row["created_at"] = NOW + timedelta(seconds=1)
    elif drift == "tool_lifecycle": transaction.tool_row["lifecycle"] = "withdrawn"
    elif drift == "tool_revoked": transaction.revoked_ids.add("tool-1")
    with pytest.raises(ValueError, match="content generate"):
        validate(transaction)
