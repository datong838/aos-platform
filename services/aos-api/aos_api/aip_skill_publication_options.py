"""Read-only, tenant-scoped exact choices for governed Skill publication.

Choices are navigation aids, never publication authority. The existing Owner
revalidates every selected reference in the write transaction.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from pydantic import Field

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_agent_registry_store import AipAgentRegistryTransitionBlocked
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_eval_contracts import AssetRevisionRef, AssetType
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.aip_skill_publication_service import PostgresSkillPublicationRouteAuthority
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


class ReleaseChoice(AipContractModel):
    publication_id: str
    release_gate_decision_id: str


class RouteChoice(AipContractModel):
    route_ref: VersionedAssetRef
    policy_ref: VersionedAssetRef


class SkillPublicationOptions(AipContractModel):
    tenant: TenantContext
    skill_id: str
    revision: int = Field(ge=1)
    release_candidates: list[ReleaseChoice]
    logic_candidates: list[VersionedAssetRef]
    route_candidates: list[RouteChoice]
    blockers: list[str]


class SkillPublicationOptionsReader:
    def __init__(self, connect_factory=None, *, runtime_store=None,
                 route_authority=None):
        self._connect = connect_factory or db_connect
        self._runtime = runtime_store or AipModelRuntimeStore(self._connect)
        self._route_authority = route_authority or PostgresSkillPublicationRouteAuthority(
            store=self._runtime)

    def read(self, scope: TenantScope, skill_id: str,
             revision: int) -> SkillPublicationOptions:
        if (type(scope) is not TenantScope or type(skill_id) is not str
                or not skill_id or skill_id != skill_id.strip()
                or type(revision) is not int or revision < 1):
            raise ValueError('exact scoped Skill publication source required')
        with self._connect(scope) as conn:
            source = conn.execute(
                """SELECT skill_id,revision,lifecycle,content_hash,canonical_logic_id
                   FROM aip_skill_template_revision WHERE skill_id=%s AND revision=%s""",
                (skill_id, revision),
            ).fetchone()
            if source is None:
                raise LookupError('exact Skill revision unavailable')
            if source['skill_id'] != skill_id or source['revision'] != revision:
                raise ValueError('Skill source identity drifted')
            if source['lifecycle'] != 'evaluated':
                return SkillPublicationOptions(
                    tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
                    skill_id=skill_id, revision=revision, release_candidates=[],
                    logic_candidates=[], route_candidates=[],
                    blockers=['SOURCE_NOT_EVALUATED'],
                )
            now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            if type(now) is not datetime or now.utcoffset() is None:
                raise ValueError('Skill candidate clock unavailable')
            target = AssetRevisionRef(
                assetType=AssetType.SKILL_TEMPLATE, assetId=skill_id,
                revision=str(revision), contentHash=source['content_hash'],
            )
            event_rows = conn.execute(
                """SELECT g.decision_id,g.target_ref AS gate_target,g.status,
                          g.invalidated_by,g.decided_at,g.expires_at,
                          e.publication_id,e.event_type,e.target_ref AS event_target,
                          e.release_gate_decision_id
                   FROM aip_release_gate_decision g
                   JOIN aip_publication_event e ON e.org_id=g.org_id
                     AND e.project_id=g.project_id
                     AND e.release_gate_decision_id=g.decision_id
                   WHERE g.org_id=%s AND g.project_id=%s
                   ORDER BY e.publication_id,e.event_id LIMIT 1001""",
                scope.key,
            ).fetchall()
            if len(event_rows) > 1000:
                raise ValueError('Skill publication choices exceed bounded read')
            grouped: dict[str, list[dict]] = defaultdict(list)
            for row in event_rows:
                grouped[row['publication_id']].append(row)
            release = []
            for publication_id, rows in sorted(grouped.items()):
                published = [row for row in rows if row['event_type'] == 'published']
                if (len(published) != 1 or len(rows) != 1):
                    continue
                row = published[0]
                if (row['status'] != 'passed' or row['invalidated_by'] is not None
                        or not row['decided_at'] <= now < row['expires_at']
                        or row['release_gate_decision_id'] != row['decision_id']
                        or AssetRevisionRef.model_validate(row['gate_target']) != target
                        or AssetRevisionRef.model_validate(row['event_target']) != target):
                    continue
                release.append(ReleaseChoice(
                    publicationId=publication_id,
                    releaseGateDecisionId=row['decision_id'],
                ))
            logic_rows = conn.execute(
                """SELECT graph_id,graph_revision,graph_hash FROM aip_logic_publication
                   WHERE org_id=%s AND project_id=%s AND graph_id=%s
                   ORDER BY graph_revision DESC LIMIT 501""",
                (*scope.key, source['canonical_logic_id']),
            ).fetchall()
            if len(logic_rows) > 500:
                raise ValueError('Skill Logic choices exceed bounded read')
            logic = [VersionedAssetRef(
                assetType='LogicRevision', assetId=row['graph_id'],
                revision=row['graph_revision'], contentHash=row['graph_hash'],
            ) for row in logic_rows]
        # Runtime Store/route authority perform their own exact scoped reads.
        # Options are non-authoritative and the final POST repeats every check.
        routes = []
        summaries = self._runtime.list_current_assets(scope, 'model_route')
        if len(summaries) > 500:
            raise ValueError('Skill route choices exceed bounded read')
        for summary in summaries:
            if summary.lifecycle.value != 'active':
                continue
            route = self._runtime.get_route(
                scope, summary.ref.asset_id, summary.ref.revision)
            if route.content_hash != summary.ref.content_hash:
                raise ValueError('Skill route choice changed during read')
            try:
                self._route_authority.require_ready(
                    scope, summary.ref, route.runtime_policy_ref,
                    evaluated_at=now)
            except AipAgentRegistryTransitionBlocked:
                continue
            routes.append(RouteChoice(routeRef=summary.ref,
                                      policyRef=route.runtime_policy_ref))
        blockers = []
        if not release:
            blockers.append('RELEASE_PUBLICATION_UNAVAILABLE')
        if not logic:
            blockers.append('LOGIC_PUBLICATION_UNAVAILABLE')
        if not routes:
            blockers.append('MODEL_ROUTE_UNAVAILABLE')
        return SkillPublicationOptions(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            skill_id=skill_id, revision=revision, release_candidates=release,
            logic_candidates=logic, route_candidates=routes, blockers=blockers,
        )
