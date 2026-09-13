"""Lifecycle-owned bounded discovery and current-authority event consumption."""
import asyncio
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_connection import connect_serializable
from aos_api.ecommerce_product_event_discovery import discover_event_candidates
from aos_api.extension_runtime.live_job_directory import LivePreparedJobDirectory
from aos_api.pipeline_control_service import PipelineControlServiceFactory
from aos_api.pipeline_controlled_runtime import _authoritative_store
from aos_api.logging_facade import get_logger

log=get_logger('aos-api.product-event-worker')


class ProductEventConsumptionWorker:
    def __init__(self,factory,directory):
        if type(factory) is not PipelineControlServiceFactory or type(directory) is not LivePreparedJobDirectory:
            raise TypeError('exact lifecycle event worker dependencies required')
        self.factory,self.directory=factory,directory
        self._cursors={};self._target_offset=0

    def _discover(self,target,after):
        scope,installation,generation=target
        with connect_serializable(scope) as conn:
            return discover_event_candidates(HostTransaction(conn),scope,installation,generation,after=after,limit=5)

    def _markings(self,scope,actor):
        with connect_serializable(scope) as conn:
            rows=conn.execute('SELECT role FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
                              (*scope.key,actor)).fetchall()
            if len(rows)!=1:
                raise PermissionError('current event worker membership required')
            labels=conn.execute("SELECT object_key FROM authz_tuple WHERE org_id=%s AND project_id=%s "
                "AND user_key=%s AND relation='bearer' AND object_key LIKE %s LIMIT 1001",
                (*scope.key,'user:'+actor,'marking:%')).fetchall()
            if len(labels)>1000:
                raise PermissionError('bounded current markings required')
            result=tuple(sorted({row['object_key'][len('marking:'):] for row in labels}))
            if any(not value or value!=value.strip() or not value.isprintable() for value in result):
                raise PermissionError('current marking identity invalid')
            return result

    async def tick(self):
        targets=self.directory.current_targets()
        self._cursors={key:value for key,value in self._cursors.items() if key in targets}
        stats=dict(targetsChecked=0,candidates=0,occurrences=0,failed=0)
        if not targets:return stats
        start=self._target_offset%len(targets)
        selected=(targets[start:]+targets[:start])[:4]
        self._target_offset=(start+len(selected))%len(targets)
        for target in selected:
            stats['targetsChecked']+=1
            try:
                rows=self._discover(target,self._cursors.get(target))
            except Exception as exc:
                stats['failed']+=1
                log.warning('product_event_discovery_failed target=%s error=%s',target,type(exc).__name__)
                continue
            if not rows:
                self._cursors.pop(target,None)
                continue
            scope,installation,generation=target
            for row in rows:
                stats['candidates']+=1
                try:
                    markings=self._markings(scope,row['actor'])
                    with _authoritative_store() as store:
                        consumer=self.factory.build_event_consumer(scope,actor=row['actor'],run_id=row['runId'],
                            control_ref=row['controlRef'],installation_id=installation,generation=generation,
                            live_directory=self.directory,markings=markings,store=store)
                        writes=await consumer.consume(row['policyId'])
                        stats['occurrences']+=sum(not item.replayed for item in writes)
                except Exception as exc:
                    stats['failed']+=1
                    log.warning('product_event_candidate_failed scope=%s policy=%s run=%s error=%s',
                        scope.key,row['policyId'],row['runId'],type(exc).__name__)
                finally:
                    self._cursors[target]=(row['policyId'],row['runId'])
            if len(rows)<5:self._cursors.pop(target,None)
        return stats

    async def serve(self,stop,*,host_ready):
        while not stop.is_set() and host_ready():
            try:
                result=await self.tick()
                if result['occurrences'] or result['failed']:
                    log.info('product_event_tick targets=%s candidates=%s occurrences=%s failed=%s',
                        result['targetsChecked'],result['candidates'],result['occurrences'],result['failed'])
            except Exception:
                log.exception('product_event_tick_failed_closed')
            try:
                await asyncio.wait_for(stop.wait(),timeout=15)
            except TimeoutError:
                continue


def build_product_event_worker(control_plane):
    factory=getattr(control_plane,'pipeline_control_factory',None)
    directory=getattr(control_plane,'live_job_directory',None)
    if factory is None or directory is None:return None
    return ProductEventConsumptionWorker(factory,directory)
