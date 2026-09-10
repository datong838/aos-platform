"""Atomically consume persisted content into existing Usage/Artifact/Budget Owners."""
from copy import deepcopy
import hashlib
from psycopg import sql
from aos_api.aip_budget_reservation_contracts import BudgetExactRef
from aos_api.aip_budget_reservation_store import AipBudgetReservationStore, canonical_hash
from aos_api.aip_task_store import AipTaskStore
from aos_api.ecommerce_content_execution_journal import ContentExecutionJournal, ContentExecutionConflict
from aos_api.ecommerce_content_usage import ContentUsageRecorder
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import (
    ContentGenerateHostService, TransactionBoundConnectFactory, _content_business_text,
)


class ContentResultConsumer:
    def __init__(self, *, context_reader, storage_schema='public'):
        self.context_reader=context_reader
        self.journal=ContentExecutionJournal(storage_schema=storage_schema)
        self.schema=storage_schema

    def consume(self, conn, scope, reservation_id):
        with conn.transaction():
            row=self.journal._reservation(conn,scope,reservation_id)
            if row['state'] not in {'submitted','unknown','settled','cost_pending'}:
                raise ContentExecutionConflict('result consumption requires submitted execution')
            evidence=self.journal.read(conn,scope,reservation_id)
            if evidence is None or evidence['result'] is None:
                raise ContentExecutionConflict('persisted content result required')
            command=evidence['command'];response=evidence['result']
            request=ContentGenerateHostService._budget_request(command)
            if request.request_hash()!=row['request_hash']:
                raise ContentExecutionConflict('content command reservation drifted')
            context=self.context_reader(conn,scope,deepcopy(command))
            if type(context) is not dict or set(context)!={'runId','productNames','channels','constraintChecks'}:
                raise ContentExecutionConflict('current business context required')
            exists=conn.execute(sql.SQL('SELECT 1 FROM {} WHERE org_id=%s AND project_id=%s AND run_id=%s AND task_id=%s').format(sql.Identifier(self.schema,'aip_task_run')),
                (*scope.key,context['runId'],request.task_ref.resource_id)).fetchone()
            if exists is None: raise ContentExecutionConflict('content run task lineage drifted')
            body=response.get('answer')
            _content_business_text(body,name='body',limit=20_000)
            for name,limit in [('productNames',50),('channels',12),('constraintChecks',50)]:
                values=context[name]
                if type(values) is not list or not 1<=len(values)<=limit or any(type(v) is not str for v in values) or len(set(values))!=len(values):
                    raise ContentExecutionConflict('business context values drifted')
                for value in values: _content_business_text(value,name=name,limit=300)
            authorities=command['authorityRefs']
            artifact={
                'taskRef':authorities['task'],'briefRef':authorities['brief'],'growthPlanRef':authorities['growth_plan'],
                'sourceArtifactRefs':command['sourceArtifactRefs'],'factSourceRefs':command['factSourceRefs'],
                'body':body,**{k:context[k] for k in ('productNames','channels','constraintChecks')},
            }
            digest=canonical_hash(artifact)
            artifact_id='artifact-'+hashlib.sha256(str(row['invocation_id']).encode()).hexdigest()[:20]
            artifact_ref={'resourceType':'ArtifactRevision','resourceId':artifact_id,'revision':1,'contentHash':'sha256:'+digest}
            artifact['artifactRef']=artifact_ref
            result_hash,usage_refs=ContentUsageRecorder(storage_schema=self.schema).record(conn,scope,reservation_id)
            bound=TransactionBoundConnectFactory(HostTransaction(conn),scope)
            AipTaskStore(bound).record_artifact(scope,context['runId'],'ecommerce-content-consumer','ecommerce_content',{
                'contentHash':digest,'schemaRef':'aos://schemas/ecommerce-readable-content/v1',
                'source':{'invocationId':str(row['invocation_id']),'providerResultHash':result_hash},
                'evidenceRefs':command['factSourceRefs'],
                'metadata':{'ecommerceGrowthContentArtifact':artifact},
            },artifact_id=artifact_id)
            budget=AipBudgetReservationStore(bound,authority_schema=self.schema)
            price=conn.execute(sql.SQL('SELECT payload FROM {} WHERE org_id=%s AND project_id=%s AND model_price_snapshot_id=%s AND revision=%s').format(sql.Identifier(self.schema,'aip_model_price_snapshot_revision')),
                (*scope.key,request.pricing_ref.resource_id,request.pricing_ref.revision)).fetchone()
            if price is None: raise ContentExecutionConflict('price authority unavailable')
            args=dict(provider_result_hash=result_hash,usage_receipt_refs=usage_refs,
                evidence_refs=(BudgetExactRef.model_validate(artifact_ref),),actor='ecommerce-content-consumer')
            if price['payload'].get('developmentCostAuthorization') is not None:
                completed=budget.complete_cost_pending(scope,reservation_id,**args)
            else:
                actual=int(row['actual_minor']) if row['state']=='settled' else budget._actual_from_usage(conn,scope,row,usage_refs)
                completed=budget.settle(scope,reservation_id,actual_minor=actual,**args)
            return {'artifact':artifact,'reservation':completed}
