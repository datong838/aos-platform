"""Derive measured usage from immutable content results via existing Owners."""
from datetime import datetime
from psycopg import sql
from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
from aos_api.aip_eval_contracts import LineageEvent, UsageReceiptIngestRequest
from aos_api.aip_telemetry_usage_service import AipTelemetryUsageService
from aos_api.aip_budget_reservation_contracts import BudgetExactRef
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.ecommerce_content_execution_journal import ContentExecutionJournal, ContentExecutionConflict, _payload
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory


class ContentUsageRecorder:
    def __init__(self, *, storage_schema='public'):
        self.journal=ContentExecutionJournal(storage_schema=storage_schema)
        self.schema=storage_schema

    def record(self, conn, scope, reservation_id):
        reservation=self.journal._reservation(conn,scope,reservation_id)
        evidence=self.journal.read(conn,scope,reservation_id)
        if evidence is None or evidence['result'] is None:
            raise ContentExecutionConflict('persisted content result required')
        response=evidence['result']
        request=conn.execute(sql.SQL('SELECT provider_ref FROM {} WHERE org_id=%s AND project_id=%s AND invocation_id=%s').format(sql.Identifier(self.schema,'aip_capability_provider_request_receipt')),(*scope.key,reservation['invocation_id'])).fetchone()
        if request is None or response.get('provider')!=request['provider_ref']['resourceId']:
            raise ContentExecutionConflict('result provider lineage drifted')
        if response.get('modality') != 'text' or any(type(response.get(k)) is not int for k in ('tokens','promptTokens','completionTokens')):
            raise ContentExecutionConflict('measured text response required')
        raw=response.get('usageReceipts')
        receipt_id=response.get('providerReceiptId')
        if not isinstance(receipt_id,str) or not receipt_id.strip() or type(raw) is not list or len(raw)!=2:
            raise ContentExecutionConflict('measured text usage required')
        quantities=[];times=[]
        for item,kind in zip(raw,('input_token','output_token'),strict=True):
            if type(item) is not dict or item.get('usageKind')!=kind or item.get('quality')!='measured' or item.get('unit')!='token' or item.get('currency') is not None:
                raise ContentExecutionConflict('measured token usage required')
            quantity=item.get('quantity')
            if type(quantity) is not int or not 0<=quantity<=9_007_199_254_740_991:
                raise ContentExecutionConflict('integer token usage required')
            instant=datetime.fromisoformat(item['observedAt'])
            if instant.utcoffset() is None:
                raise ContentExecutionConflict('aware usage observation required')
            quantities.append(quantity);times.append(instant)
        if response.get('promptTokens')!=quantities[0] or response.get('completionTokens')!=quantities[1] or response.get('tokens')!=sum(quantities):
            raise ContentExecutionConflict('token totals drifted')
        result_hash=_payload(response)[1]
        lineage=str(reservation['invocation_id'])
        owner=AipEvalAuthorityStore(TransactionBoundConnectFactory(HostTransaction(conn),scope))
        owner.append_lineage_event(scope,LineageEvent(tenant={'orgId':scope.org_id,'projectId':scope.project_id},
            eventId='content-result:'+lineage,lineageId=lineage,rootType='capability_invocation',rootId=lineage,
            sequence=1,eventType='model',payloadHash=result_hash,quality='measured',
            occurredAt=max(times),observedAt=max(times),sourceKind='capability_provider_result',
            sourceId=str(reservation_id),sourceHash=result_hash))
        service=AipTelemetryUsageService(owner);refs=[]
        for index,item in enumerate(raw):
            receipt=service.ingest_usage(scope,UsageReceiptIngestRequest(provider=response['provider'],
                providerReceiptId=f"{receipt_id}:{index}:{item['usageKind']}",lineageId=lineage,
                usageKind=item['usageKind'],quantity=quantities[index],unit='token',quality='measured',
                sourceHash=result_hash,observedAt=times[index]))
            row=conn.execute(sql.SQL('SELECT receipt_id,provider,provider_receipt_id,lineage_id,usage_kind,quantity,unit,currency,quality,source_hash,observed_at FROM {} WHERE org_id=%s AND project_id=%s AND receipt_id=%s').format(sql.Identifier(self.schema,'aip_usage_receipt')),(*scope.key,receipt.receipt_id)).fetchone()
            refs.append(BudgetExactRef(resourceType='UsageReceipt',resourceId=receipt.receipt_id,revision=1,contentHash=canonical_hash(dict(row),prefixed=True)))
        return result_hash,tuple(refs)
