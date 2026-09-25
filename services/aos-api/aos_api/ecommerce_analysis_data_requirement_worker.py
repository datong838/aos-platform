"""Lifecycle-owned fixed consumer for original analysis DataRequirement deliveries."""
from __future__ import annotations

import asyncio
from uuid import uuid4

from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.data_requirement_outbox_store import DataRequirementOutboxStore
from aos_api.ecommerce_analysis_data_requirement_route import AnalysisDataRequirementRouteReader
from aos_api.ecommerce_growth_runtime_connection import connect_serializable
from aos_api.extension_runtime.live_job_directory import LivePreparedJobDirectory
from aos_api.logging_facade import get_logger
from aos_api.pipeline_control_service import PipelineControlServiceFactory
from aos_api.pipeline_controlled_runtime import _authoritative_store
from aos_api.tenant_scope import TenantScope

log = get_logger('aos-api.analysis-data-requirement-worker')
_TOPIC = 'data.requirement.request'


class AnalysisDataRequirementWorker:
    def __init__(self, factory, directory, *, lease_seconds=300):
        if type(factory) is not PipelineControlServiceFactory or type(directory) is not LivePreparedJobDirectory:
            raise TypeError('exact lifecycle analysis worker dependencies required')
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600:
            raise ValueError('bounded analysis worker lease required')
        self.factory, self.directory = factory, directory
        self.lease_seconds = lease_seconds
        self._worker_id = 'analysis-data-' + uuid4().hex
        self._scope_offset = 0
        self._outbox = DataRequirementOutboxStore(connect_serializable)

    def _scopes(self):
        targets = self.directory.current_targets()
        scopes = tuple(sorted({target[0] for target in targets}, key=lambda value: value.key))
        if len(scopes) > 1000:
            raise RuntimeError('bounded current analysis worker scopes required')
        return scopes

    @staticmethod
    def _markings(scope, actor):
        with connect_serializable(scope) as conn:
            rows = conn.execute(
                'SELECT role FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
                (*scope.key, actor),
            ).fetchall()
            if len(rows) != 1:
                raise PermissionError('current analysis worker membership required')
            labels = conn.execute(
                "SELECT object_key FROM authz_tuple WHERE org_id=%s AND project_id=%s "
                "AND user_key=%s AND relation='bearer' AND object_key LIKE %s LIMIT 1001",
                (*scope.key, 'user:' + actor, 'marking:%'),
            ).fetchall()
            if len(labels) > 1000:
                raise PermissionError('bounded current analysis markings required')
            result = tuple(sorted({row['object_key'][len('marking:'):] for row in labels}))
            if any(not value or value != value.strip() or not value.isprintable() for value in result):
                raise PermissionError('current analysis marking identity invalid')
            return result

    def _route(self, scope, claim, *, reconcile):
        services = self.factory.build(scope)
        reader = AnalysisDataRequirementRouteReader(
            claims=services.claims, connect_factory=connect_serializable,
        )
        return reader.read_unknown(scope, claim) if reconcile else reader.read(scope, claim)

    def _settle_claimed_failure(self, scope, claim, reason_code):
        try:
            self._outbox.fail(scope, claim.outbox_id, claim.lease_token, reason_code=reason_code)
        except Exception:
            log.warning('analysis_data_requirement_fail_fenced scope=%s outbox=%s', scope.key, claim.outbox_id)

    def _settle_unknown(self, scope, claim, reason_code):
        try:
            self._outbox.mark_unknown(
                scope, claim.outbox_id, claim.lease_token, reason_code=reason_code,
            )
        except Exception:
            log.warning('analysis_data_requirement_unknown_fenced scope=%s outbox=%s', scope.key, claim.outbox_id)

    def _run_claim(self, scope, claim, *, reconcile):
        try:
            route = self._route(scope, claim, reconcile=reconcile)
            self.directory.resolve(scope=scope, installation_id=route.installation_id,
                                   generation=route.generation)
            markings = self._markings(scope, route.actor)
        except Exception:
            if not reconcile:
                self._settle_claimed_failure(scope, claim, 'CURRENT_ROUTE_REJECTED')
            return 'failed'
        try:
            with _authoritative_store() as store:
                coordinator = self.factory.build_analysis_snapshot_coordinator(
                    scope, route=route, live_directory=self.directory,
                    markings=markings, store=store,
                )
                try:
                    result = coordinator.run(route=route)
                except Exception:
                    if not reconcile:
                        self._settle_unknown(scope, claim, 'COORDINATION_RESULT_UNKNOWN')
                    return 'unknown'
        except Exception:
            if not reconcile:
                self._settle_unknown(scope, claim, 'COORDINATION_RESULT_UNKNOWN')
            return 'unknown'
        try:
            fulfillment = InvestigationExactRef.model_validate(result['fulfillmentRef'])
            analysis = InvestigationExactRef.model_validate(result['receiptRef'])
            transition = (self._outbox.reconcile_completed if reconcile else self._outbox.complete)(
                scope, claim, fulfillment, analysis,
            )
            return 'replayed' if transition.replayed else 'completed'
        except Exception:
            if not reconcile:
                self._settle_unknown(scope, claim, 'OUTBOX_COMPLETION_RESULT_UNKNOWN')
            return 'unknown'

    def run_scope_once(self, scope):
        if type(scope) is not TenantScope:
            raise TypeError('exact analysis worker tenant required')
        ambiguous = self._outbox.read_ambiguous_next(scope, topic=_TOPIC)
        if ambiguous is not None:
            log.warning('analysis_data_requirement_ambiguous_frozen scope=%s outbox=%s',
                        scope.key, ambiguous.outbox_id)
            return 'unknown'
        claim = self._outbox.claim_pending_next(
            scope, topic=_TOPIC, worker_id=self._worker_id,
            lease_token='analysis-data-lease-' + uuid4().hex,
            lease_seconds=self.lease_seconds,
        )
        return 'idle' if claim is None else self._run_claim(scope, claim, reconcile=False)

    @staticmethod
    async def _run_thread(call, *args):
        task = asyncio.create_task(asyncio.to_thread(call, *args))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            try:
                await task
            except Exception:
                pass
            raise

    async def tick(self):
        scopes = self._scopes()
        stats = dict(scopesChecked=0, completed=0, replayed=0, unknown=0, failed=0)
        if not scopes:
            return stats
        start = self._scope_offset % len(scopes)
        selected = (scopes[start:] + scopes[:start])[:4]
        self._scope_offset = (start + len(selected)) % len(scopes)
        for scope in selected:
            stats['scopesChecked'] += 1
            try:
                outcome = await self._run_thread(self.run_scope_once, scope)
                if outcome in stats:
                    stats[outcome] += 1
            except asyncio.CancelledError:
                raise
            except Exception:
                stats['failed'] += 1
                log.warning('analysis_data_requirement_tick_failed scope=%s', scope.key)
        return stats

    async def serve(self, stop, *, host_ready):
        while not stop.is_set() and host_ready():
            try:
                result = await self.tick()
                if any(result[key] for key in ('completed', 'replayed', 'unknown', 'failed')):
                    log.info('analysis_data_requirement_tick %s', result)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception('analysis_data_requirement_worker_failed_closed')
            try:
                await asyncio.wait_for(stop.wait(), timeout=15)
            except TimeoutError:
                continue


def build_analysis_data_requirement_worker(control_plane):
    factory = getattr(control_plane, 'pipeline_control_factory', None)
    directory = getattr(control_plane, 'live_job_directory', None)
    if factory is None or directory is None:
        return None
    return AnalysisDataRequirementWorker(factory, directory)


__all__ = ['AnalysisDataRequirementWorker', 'build_analysis_data_requirement_worker']
