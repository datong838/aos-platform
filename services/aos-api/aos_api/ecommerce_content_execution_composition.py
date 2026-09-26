"""Current-authority preparation for one durable ecommerce content command.

This module never submits a Provider request. The original worker owns that
commit boundary, and the exact invoker owns the subsequent remote call.
"""
import asyncio
import hashlib
from types import SimpleNamespace

from psycopg import sql

from aos_api.aip_model_runtime_contracts import ModelRuntimeReadiness
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.aip_model_governance_policy_store import AipModelGovernancePolicyStore
from aos_api.aip_network_policy_store import AipNetworkPolicyStore
from aos_api.aip_runtime_guard_policy_store import AipRuntimeGuardPolicyStore
from aos_api.aip_exact_provider_invoker import ExactProviderInvoker
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef,GrowthPlanLifecycle
from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore
from aos_api.ecommerce_content_execution_journal import ContentExecutionConflict,ContentExecutionJournal
from aos_api.ecommerce_content_execution_journal import _payload
from aos_api.ecommerce_content_execution_worker import ContentExecutionWorker,PreparedContentInvocation
from aos_api.ecommerce_content_result_consumer import ContentResultConsumer
from aos_api.ecommerce_growth_host_ports import HostTransaction, LockedEcommerceGrowthHostPort
from aos_api.ecommerce_growth_runtime_connection import connect_serializable
from aos_api.ecommerce_growth_runtime_adapters import (
    ContentGenerateHostService,
    ReviewAdvanceHostService,
    TransactionBoundConnectFactory,
    _strict_content_generate_command,
)
from aos_api.tenant_scope import TenantScope
from aos_api.aip_budget_reservation_store import canonical_hash


class CurrentContentPreparation:
    """Re-lock the current installation and content authorities before submit."""

    operation_id = 'ecommerce_growth_content_generate'
    data_classification = 'approved_internal_knowledge'

    @staticmethod
    def _runtime_row(conn, scope, command):
        return conn.execute('''SELECT * FROM public.ecommerce_growth_runtime_command_receipt
            WHERE org_id=%s AND project_id=%s AND operation_id=%s AND idempotency_key=%s''',
            (*scope.key,CurrentContentPreparation.operation_id,command['idempotencyKey'])).fetchone()

    @staticmethod
    def _lock_dispatch(conn, scope, row):
        ref=SimpleNamespace(org_id=scope.org_id,project_id=scope.project_id,
            operation_id=CurrentContentPreparation.operation_id,handler_kind='extension',
            dispatch_revision=row['dispatch_revision'],installation_id=row['installation_id'],
            generation=row['generation'],execution_epoch=row['execution_epoch'],
            cutover_group_id=row['cutover_group_id'],
            cutover_group_revision=row['cutover_group_revision'])
        return LockedEcommerceGrowthHostPort._lock_and_revalidate(conn,scope,ref)

    @staticmethod
    def _resolve_route(transaction, scope, route_id, checked_at):
        bound=TransactionBoundConnectFactory(transaction,scope)
        return AipModelRuntimeResolver(AipModelRuntimeStore(bound)).resolve(
            scope,route_id,now=checked_at)

    @staticmethod
    def _statement(text, source_numbers):
        if not source_numbers:
            raise ContentExecutionConflict('approved statement lacks a source')
        return text+'（来源 '+','.join('E'+str(number) for number in source_numbers)+'）'

    @classmethod
    def _prompt(cls, method, *, max_input_tokens):
        if type(max_input_tokens) is not int or max_input_tokens <= 0:
            raise ContentExecutionConflict('content input token cap is invalid')
        source_numbers={
            (ref.resource_type,ref.resource_id,ref.revision,ref.content_hash):index
            for index,ref in enumerate(method.evidence_refs,start=1)
        }
        def statement(value):
            try:
                numbers=[source_numbers[(ref.resource_type,ref.resource_id,ref.revision,ref.content_hash)]
                    for ref in value.evidence_refs]
            except KeyError:
                raise ContentExecutionConflict('approved statement source drifted') from None
            return cls._statement(value.text,numbers)
        lines=[
            '请仅依据以下已批准的内部经营方法，生成供人工评审的中文文字内容草稿。不得发布、联系客户、编造销量或把未知事项写成已证实事实。',
            '商品：'+method.product_label,
            '客群假设：'+statement(method.audience_hypothesis),
            '使用场景：'+statement(method.scenario),
            '适用：'+'；'.join(statement(item) for item in method.fit_for),
            '不适用：'+'；'.join(statement(item) for item in method.not_fit_for),
            '可用价值主张：'+'；'.join(statement(item) for item in method.proposed_value_claims),
            '未知事实（必须标待核）：'+'；'.join(method.unknown_facts),
            '禁止主张：'+'；'.join(method.prohibited_claims),
            '渠道：'+'；'.join(method.channels),
            '时间窗口：'+method.time_window,
            '人工交接条件：'+method.handoff_condition,
            '输出正文、适用渠道和逐项约束核查；来源编号只表示已批准方法的引用，不得声称见过原始商城数据。',
        ]
        prompt='\n'.join(lines)
        # A byte cap is conservative for tokenized text and never truncates facts.
        if len(prompt.encode('utf-8'))>max_input_tokens:
            raise ContentExecutionConflict('content prompt exceeds approved input token cap')
        return prompt

    def __call__(self, conn, scope, command):
        parsed=_strict_content_generate_command(command)
        row=self._runtime_row(conn,scope,command)
        if (row is None or row['request_hash']!=command['requestHash']
            or type(row['response']) is not dict
            or row['response'].get('state')!='PENDING'):
            raise ContentExecutionConflict('current content PENDING Receipt unavailable')
        snapshot=self._lock_dispatch(conn,scope,row)
        if snapshot.runtime_revision!=row['runtime_revision']:
            raise ContentExecutionConflict('content runtime revision drifted')
        transaction=HostTransaction(conn)
        service=ContentGenerateHostService()
        if service.verify_receipt(transaction=transaction,scope=scope,dispatch=snapshot,
            command=command,receipt=row['response'])!=row['response']:
            raise ContentExecutionConflict('content PENDING Receipt drifted')
        service.revalidate(transaction=transaction,scope=scope,dispatch=snapshot,command=command)
        plan=ReviewAdvanceHostService._revalidate_growth_plan(
            transaction=transaction,scope=scope,
            command={'growthPlanRef':command['authorityRefs']['growth_plan']})
        if plan.sales_weapon_method is None:
            raise ContentExecutionConflict('approved sales weapon method unavailable')
        route_ref=parsed['authorities']['model_route']
        resolution=self._resolve_route(transaction,scope,route_ref.resource_id,snapshot.checked_at)
        price_ref=parsed['authorities']['pricing']
        if (resolution.readiness is not ModelRuntimeReadiness.READY
            or (resolution.route.asset_id,resolution.route.revision,resolution.route.content_hash)
                !=(route_ref.resource_id,route_ref.revision,route_ref.content_hash.removeprefix('sha256:'))
            or resolution.selected_price_snapshot is None
            or (resolution.selected_price_snapshot.asset_id,resolution.selected_price_snapshot.revision,
                resolution.selected_price_snapshot.content_hash)
                !=(price_ref.resource_id,price_ref.revision,price_ref.content_hash.removeprefix('sha256:'))):
            raise ContentExecutionConflict('content exact model route or price unavailable')
        prompt=self._prompt(plan.sales_weapon_method,max_input_tokens=command['maxInputTokens'])
        return PreparedContentInvocation(resolution,prompt,self.data_classification,
            max_output_tokens=command['maxOutputTokens'])


class CurrentContentRunner:
    """One bounded pass over committed PENDING commands, never an implicit timer."""

    def __init__(self, *, connect_factory=connect_serializable, storage_schema='public'):
        self.connect=connect_factory
        self.journal=ContentExecutionJournal(storage_schema=storage_schema)
        guard=AipRuntimeGuardPolicyStore(connect_factory)
        invoker=ExactProviderInvoker(
            model_store=AipModelRuntimeStore(connect_factory),
            guard_store=guard,
            network_store=AipNetworkPolicyStore(connect_factory,guard_policy_store=guard),
            governance_store=AipModelGovernancePolicyStore(connect_factory),
        )
        self.worker=ContentExecutionWorker(connect_factory,
            prepare=CurrentContentPreparation(),invoke=invoker,
            storage_schema=storage_schema)
        self.consumer=ContentResultConsumer(
            context_reader=CurrentContentContextReader(),storage_schema=storage_schema)
        self.status_reader=CurrentContentStatusReader(storage_schema=storage_schema)

    def run_pending(self, scope, *, limit=32):
        if type(scope) is not TenantScope:
            raise TypeError('trusted tenant scope required')
        with self.connect(scope) as conn:
            reservation_ids=self.journal.list_held(conn,scope,limit=limit)
        statuses=[]
        for reservation_id in reservation_ids:
            try:
                result=self.worker.run_one(scope,reservation_id)
            except ContentExecutionConflict:
                # A pre-submit authority conflict blocks this item, not the queue.
                statuses.append({'reservationId':reservation_id,'status':'BLOCKED_CURRENT_AUTHORITY'})
                continue
            statuses.append({'reservationId':reservation_id,'status':result['status']})
        return statuses

    def run_recorded(self, scope, *, limit=32):
        if type(scope) is not TenantScope:
            raise TypeError('trusted tenant scope required')
        with self.connect(scope) as conn:
            reservation_ids=self.journal.list_recorded(conn,scope,limit=limit)
        statuses=[]
        for reservation_id in reservation_ids:
            try:
                with self.connect(scope) as conn:
                    self.consumer.consume(conn,scope,reservation_id)
            except ContentExecutionConflict:
                statuses.append({'reservationId':reservation_id,'status':'BLOCKED_ACCOUNTING'})
                continue
            with self.connect(scope) as conn:
                status=self.status_reader(conn,scope,reservation_id)
            statuses.append({'reservationId':reservation_id,'status':status})
        return statuses

    def run_once(self, scope, *, limit=32):
        recorded_before=self.run_recorded(scope,limit=limit)
        pending=self.run_pending(scope,limit=limit)
        recorded_after=self.run_recorded(scope,limit=limit)
        return {'recordedBefore':recorded_before,'pending':pending,
            'recordedAfter':recorded_after}

    async def serve(self, stop, *, host_ready, interval_seconds=15):
        if type(interval_seconds) is not int or not 1 <= interval_seconds <= 300:
            raise ValueError('content worker interval is invalid')
        scope=TenantScope('org-org','dev-project')
        while not stop.is_set():
            if not host_ready():
                raise RuntimeError('content worker Runtime Host became unavailable')
            await asyncio.to_thread(self.run_once,scope)
            try:
                await asyncio.wait_for(stop.wait(),timeout=interval_seconds)
            except TimeoutError:
                pass


class CurrentContentContextReader:
    """Historical exact context only for accounting for an already recorded result."""

    def __call__(self, conn, scope, command):
        parsed=_strict_content_generate_command(command)
        authorities=parsed['authorities']
        task_id=authorities['task'].resource_id
        capacity_id=authorities['capacity_reservation'].resource_id
        row=conn.execute('''SELECT a.task_id,a.task_run_id AS run_id,t.task_id AS run_task_id
            FROM public.aip_model_capacity_reservation c
            JOIN public.aip_agent_run a ON a.org_id=c.org_id AND a.project_id=c.project_id
                AND a.agent_run_id=c.agent_run_id
            JOIN public.aip_task_run t ON t.org_id=a.org_id AND t.project_id=a.project_id
                AND t.run_id=a.task_run_id
            WHERE c.org_id=%s AND c.project_id=%s AND c.reservation_id=%s''',
            (*scope.key,capacity_id)).fetchone()
        if (row is None or row['task_id']!=task_id or row['run_task_id']!=task_id
            or type(row['run_id']) is not str or not row['run_id']):
            raise ContentExecutionConflict('content AgentRun TaskRun lineage unavailable')
        plan_ref=authorities['growth_plan']
        exact=AnalystExactRef(resource_type='GrowthPlanRevision',
            resource_id=plan_ref.resource_id,revision=plan_ref.revision,
            content_hash=plan_ref.content_hash.removeprefix('sha256:'))
        store=EcommerceAnalystAuthorityStore(
            TransactionBoundConnectFactory(HostTransaction(conn),scope))
        plan=store.get_plan_exact(scope,exact)
        if plan.lifecycle!=GrowthPlanLifecycle.APPROVED or plan.sales_weapon_method is None:
            raise ContentExecutionConflict('historical approved content method unavailable')
        method=plan.sales_weapon_method
        return {
            'runId':row['run_id'],
            'productNames':[method.product_label],
            'channels':list(method.channels),
            'constraintChecks':(
                ['待核：'+value for value in method.unknown_facts]
                +['禁止主张：'+value for value in method.prohibited_claims]
            ),
        }


class CurrentContentStatusReader:
    """Independent readback; a consumed result alone is never completion."""

    def __init__(self, *, storage_schema='public'):
        self.journal=ContentExecutionJournal(storage_schema=storage_schema)
        self.schema=storage_schema

    def __call__(self, conn, scope, reservation_id):
        if type(scope) is not TenantScope:
            raise TypeError('trusted tenant scope required')
        row=conn.execute(sql.SQL('''SELECT * FROM {} WHERE org_id=%s AND project_id=%s
            AND reservation_id=%s''').format(sql.Identifier(self.schema,'aip_budget_reservation')),
            (*scope.key,reservation_id)).fetchone()
        if row is None or row['operation_id']!='ecommerce_growth_content_generate':
            raise ContentExecutionConflict('content reservation unavailable')
        evidence=self.journal.read(conn,scope,reservation_id)
        if evidence is None or evidence['result'] is None:
            return 'HELD' if row['state']=='held' else 'RECONCILIATION_REQUIRED'
        result_hash=_payload(evidence['result'])[1]
        if row['state'] not in {'settled','cost_pending'}:
            return 'RESULT_RECORDED_UNSETTLED'
        request_ref=row['provider_request_receipt_ref']
        provider_ref=row['provider_receipt_ref']
        usage_refs=row['usage_receipt_refs']
        if (type(request_ref) is not dict or type(provider_ref) is not dict
            or type(usage_refs) is not list or len(usage_refs)!=2):
            raise ContentExecutionConflict('content completion references incomplete')
        request=conn.execute(sql.SQL('''SELECT request_receipt_id,revision,content_hash
            FROM {} WHERE org_id=%s AND project_id=%s AND invocation_id=%s''').format(
                sql.Identifier(self.schema,'aip_capability_provider_request_receipt')),
            (*scope.key,row['invocation_id'])).fetchone()
        if (request is None or str(request['request_receipt_id'])!=request_ref.get('resourceId')
            or request['revision']!=request_ref.get('revision')
            or request['content_hash']!=request_ref.get('contentHash')):
            raise ContentExecutionConflict('provider request Receipt readback drifted')
        provider=conn.execute(sql.SQL('''SELECT provider_receipt_id,revision,content_hash,
            provider_result_hash,outcome,evidence_refs FROM {} WHERE org_id=%s AND project_id=%s
            AND invocation_id=%s AND provider_result_hash=%s''').format(
                sql.Identifier(self.schema,'aip_capability_provider_receipt')),
            (*scope.key,row['invocation_id'],result_hash)).fetchone()
        if (provider is None or provider['outcome']!='completed'
            or str(provider['provider_receipt_id'])!=provider_ref.get('resourceId')
            or provider['revision']!=provider_ref.get('revision')
            or provider['content_hash']!=provider_ref.get('contentHash')
            or type(provider['evidence_refs']) is not list or len(provider['evidence_refs'])!=1):
            raise ContentExecutionConflict('provider result Receipt readback drifted')
        artifact_ref=provider['evidence_refs'][0]
        expected_id='artifact-'+hashlib.sha256(str(row['invocation_id']).encode()).hexdigest()[:20]
        if (type(artifact_ref) is not dict or artifact_ref.get('resourceType')!='ArtifactRevision'
            or artifact_ref.get('resourceId')!=expected_id or artifact_ref.get('revision')!=1):
            raise ContentExecutionConflict('content Artifact reference drifted')
        artifact=conn.execute(sql.SQL('''SELECT artifact_id,run_id,artifact_type,schema_ref,
            content_hash,metadata,source FROM {} WHERE org_id=%s AND project_id=%s AND artifact_id=%s''').format(
                sql.Identifier(self.schema,'aip_artifact')),
            (*scope.key,expected_id)).fetchone()
        payload=None if artifact is None else artifact['metadata'].get('ecommerceGrowthContentArtifact')
        if (artifact is None or artifact['artifact_type']!='ecommerce_content'
            or artifact['schema_ref']!='aos://schemas/ecommerce-readable-content/v1'
            or type(payload) is not dict or payload.get('artifactRef')!=artifact_ref
            or type(payload.get('body')) is not str or not payload['body'].strip()
            or artifact['content_hash']!=artifact_ref.get('contentHash','').removeprefix('sha256:')
            or canonical_hash({k:v for k,v in payload.items() if k!='artifactRef'})!=artifact['content_hash']
            or artifact['source'].get('invocationId')!=str(row['invocation_id'])
            or artifact['source'].get('providerResultHash')!=result_hash):
            raise ContentExecutionConflict('readable content Artifact readback drifted')
        task=conn.execute(sql.SQL('''SELECT task_id FROM {} WHERE org_id=%s AND project_id=%s
            AND run_id=%s''').format(sql.Identifier(self.schema,'aip_task_run')),
            (*scope.key,artifact['run_id'])).fetchone()
        if task is None or task['task_id']!=row['task_ref'].get('resourceId'):
            raise ContentExecutionConflict('content Artifact TaskRun lineage drifted')
        kinds=set()
        for ref in usage_refs:
            if type(ref) is not dict or ref.get('resourceType')!='UsageReceipt' or ref.get('revision')!=1:
                raise ContentExecutionConflict('content Usage reference drifted')
            usage=conn.execute(sql.SQL('''SELECT receipt_id,provider,provider_receipt_id,
                lineage_id,usage_kind,quantity,unit,currency,quality,source_hash,observed_at
                FROM {} WHERE org_id=%s AND project_id=%s AND receipt_id=%s''').format(
                    sql.Identifier(self.schema,'aip_usage_receipt')),
                (*scope.key,ref.get('resourceId'))).fetchone()
            if (usage is None or usage['source_hash']!=result_hash
                or usage['lineage_id']!=str(row['invocation_id'])
                or canonical_hash(dict(usage),prefixed=True)!=ref.get('contentHash')):
                raise ContentExecutionConflict('measured content Usage readback drifted')
            kinds.add(usage['usage_kind'])
        if kinds!={'input_token','output_token'}:
            raise ContentExecutionConflict('measured content Usage kinds drifted')
        return 'COST_PENDING' if row['state']=='cost_pending' else 'COMPLETED'
