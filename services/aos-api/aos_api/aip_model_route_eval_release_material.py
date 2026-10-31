"""Read the immutable Route manifest attached to one final proof.

This module exposes verified business-source identities only.  It never loads a
credential, creates a Source command, opens a connection, commits, or grants
execution/release authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_eval_contracts import EvalReportRevision
from aos_api.aip_model_route_eval_finalization_proof import (
    RouteEvalFinalizationProof,
    RouteEvalFinalizationProofStore,
    canonical_route_eval_finalization_proof,
)
from aos_api.aip_model_route_eval_manifest import RouteEvalApplication
from aos_api.aip_model_route_eval_signatures import _manifest
from aos_api.aip_route_release_request_context import RouteReleaseRequestContext
from aos_api.aip_model_runtime_contracts import ModelRouteRevision, ModelRuntimeLifecycle
from aos_api.tenant_scope import TenantScope


class RouteEvalReleaseMaterialRejected(RuntimeError):
    """Safe fail-closed category without manifest bytes in its message."""


class RouteEvalReleaseAssemblyRejected(RuntimeError):
    """Safe assembler rejection without credentials or internal evidence."""


@dataclass(frozen=True)
class VerifiedRouteEvalReleaseMaterial:
    execution_id: str
    manifest_hash: str
    manifest_bytes: bytes
    sources: tuple[VersionedAssetRef, ...]
    execution_allowed: bool = False


def read_verified_route_eval_release_material(conn, *, scope: TenantScope,
        proof: RouteEvalFinalizationProof) -> VerifiedRouteEvalReleaseMaterial:
    """Read all and only Source identities from the persisted final manifest."""
    try:
        if (type(scope) is not TenantScope or scope.key != ("org-org", "dev-project")
            or type(proof) is not RouteEvalFinalizationProof
            or (proof.tenant.org_id, proof.tenant.project_id) != scope.key):
            raise ValueError
        canonical_route_eval_finalization_proof(proof)
        store = RouteEvalFinalizationProofStore()
        stored = store.read(conn, scope, proof.execution_id)
        if stored != proof:
            raise ValueError
        row = conn.execute("""SELECT manifest_hash,manifest_payload
            FROM public.aip_route_eval_release_material
            WHERE org_id=%s AND project_id=%s AND execution_id=%s""",
            (*scope.key, proof.execution_id)).fetchone()
        if type(row) is not dict:
            raise ValueError
        payload = bytes(row["manifest_payload"])
        if (row.get("manifest_hash") != proof.manifest_hash
            or hashlib.sha256(payload).hexdigest() != proof.manifest_hash):
            raise ValueError
        body = _manifest(payload)
        if "routeApplication" not in body or "modelPlan" in body:
            raise ValueError
        app = RouteEvalApplication.model_validate(body["routeApplication"])
        expected = [(item.case_id, item.purpose) for item in app.calls]
        finalized = [(item.case_id, item.purpose) for item in proof.calls]
        if ((app.tenant.org_id, app.tenant.project_id) != scope.key
            or not proof.execution_id == body["executionId"] == app.execution_id
            or not proof.context_binding_hash == body["contextBindingHash"]
                == app.context_binding_hash
            or expected != finalized):
            raise ValueError
        indexed = {(item.source_ref.asset_type, item.source_ref.asset_id,
            item.source_ref.revision, item.source_ref.content_hash): item.source_ref
            for item in app.calls}
        sources = tuple(indexed[key] for key in sorted(indexed))
        return VerifiedRouteEvalReleaseMaterial(execution_id=proof.execution_id,
            manifest_hash=proof.manifest_hash, manifest_bytes=payload, sources=sources)
    except RouteEvalReleaseMaterialRejected:
        raise
    except Exception:
        raise RouteEvalReleaseMaterialRejected(
            "exact persisted Route release material required") from None


class RouteEvalReleaseEvidenceAssembler:
    """Build and immediately verify request-local Route release evidence."""

    def build(self, conn, *, scope: TenantScope, report: EvalReportRevision,
            request_context: RouteReleaseRequestContext):
        try:
            if (type(scope) is not TenantScope
                or scope.key != ("org-org", "dev-project")
                or type(report) is not EvalReportRevision
                or (report.tenant.org_id, report.tenant.project_id) != scope.key
                or type(request_context) is not RouteReleaseRequestContext
                or (request_context.principal.org_id,
                    request_context.principal.project_id) != scope.key):
                raise ValueError
            from aos_api.aip_model_route_eval_proof_authority import (
                RouteEvalReleaseEvidence,
            )
            from aos_api.aip_model_route_eval_report_proof_reader import (
                read_verified_route_eval_report_from_persistence,
            )
            from aos_api.aip_provider_capacity_source_contracts import (
                ProviderCapacityConsumptionCommand,
            )

            report_proof = read_verified_route_eval_report_from_persistence(
                conn, scope=scope, report=report)
            material = read_verified_route_eval_release_material(
                conn, scope=scope, proof=report_proof.proof)
            commands = tuple(ProviderCapacityConsumptionCommand(
                schemaVersion=1,
                tenant={"orgId": scope.org_id, "projectId": scope.project_id},
                bearerToken=request_context.bearer_token,
                sourceRef=source.model_dump(mode="json", by_alias=True))
                for source in material.sources)
            evidence = RouteEvalReleaseEvidence(
                manifest_bytes=material.manifest_bytes,
                source_commands=commands)
            return evidence
        except RouteEvalReleaseAssemblyRejected:
            raise
        except Exception:
            raise RouteEvalReleaseAssemblyRejected(
                "current business source review required") from None

    def build_for_route(self, conn, *, scope: TenantScope,
            route: ModelRouteRevision,
            request_context: RouteReleaseRequestContext):
        """Assemble the exact persisted report for the current active Route.

        The resolver immediately consumes the returned evidence in the same
        transaction and remains the authority that verifies gate/publication
        currency.  This method only locates their exact immutable lineage.
        """
        try:
            if (type(scope) is not TenantScope
                or scope.key != ("org-org", "dev-project")
                or type(route) is not ModelRouteRevision
                or (route.tenant.org_id, route.tenant.project_id) != scope.key
                or route.lifecycle is not ModelRuntimeLifecycle.ACTIVE
                or route.eval_gate_ref is None
                or route.eval_gate_ref.asset_type != "EvalGateDecision"):
                raise ValueError
            from aos_api.aip_model_runtime_store import evaluation_candidate_ref
            from aos_api.aip_release_publication_service import (
                AipReleasePublicationService,
            )

            gate_row = conn.execute(
                """SELECT * FROM aip_release_gate_decision
                   WHERE org_id=%s AND project_id=%s AND decision_id=%s""",
                (*scope.key, route.eval_gate_ref.asset_id),
            ).fetchone()
            if gate_row is None:
                raise ValueError
            gate = AipReleasePublicationService._gate_from_row(scope, gate_row)
            if (gate.decision_hash != route.eval_gate_ref.content_hash
                or gate.target.asset_type.value != "model_route"
                or gate.target.asset_id != route.route_id
                or gate.target.revision != str(route.revision)
                or gate.target.content_hash
                    != evaluation_candidate_ref(route).content_hash):
                raise ValueError
            report_row = conn.execute(
                """SELECT * FROM aip_eval_report_revision
                   WHERE org_id=%s AND project_id=%s
                     AND report_id=%s AND revision=%s""",
                (*scope.key, gate.eval_report.artifact_id,
                    int(gate.eval_report.revision)),
            ).fetchone()
            if report_row is None:
                raise ValueError
            report = AipReleasePublicationService._report_from_row(scope, report_row)
            if (report.content_hash != gate.eval_report.content_hash
                or report.target != gate.target):
                raise ValueError
            return self.build(conn, scope=scope, report=report,
                request_context=request_context)
        except RouteEvalReleaseAssemblyRejected:
            raise
        except Exception:
            raise RouteEvalReleaseAssemblyRejected(
                "current business source review required") from None

    def verify(self, conn, *, scope: TenantScope, report: EvalReportRevision,
            request_context: RouteReleaseRequestContext,
            publication_id: str | None = None):
        try:
            if (publication_id is not None and (
                type(publication_id) is not str
                or publication_id != publication_id.strip()
                or not 1 <= len(publication_id) <= 200)):
                raise ValueError
            from aos_api.aip_model_route_eval_proof_authority import (
                VerifiedRouteEvalReleaseEvidence,
                verify_route_eval_release_evidence,
            )
            evidence = self.build(conn, scope=scope, report=report,
                request_context=request_context)
            verified = verify_route_eval_release_evidence(
                conn, scope=scope, report=report, evidence=evidence,
                publication_id=publication_id)
            if type(verified) is not VerifiedRouteEvalReleaseEvidence:
                raise ValueError
            return verified
        except RouteEvalReleaseAssemblyRejected:
            raise
        except Exception:
            raise RouteEvalReleaseAssemblyRejected(
                "current business source review required") from None
