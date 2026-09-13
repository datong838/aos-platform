"""Immutable routing to the first proven batch; never execution permission."""
from uuid import UUID
import re
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope


class ProductEventOriginStore:
    def __init__(self,transaction,scope):
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError('exact origin Host transaction and scope required')
        self.tx,self.scope=transaction,scope

    def _scope(self):
        row=self.tx.execute("SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,"
                            "current_setting('aos.project_id',true) AS project_id").fetchone()
        if row is None or (row['role'],row['org_id'],row['project_id'])!=('aos_runtime',*self.scope.key):
            raise PermissionError('current origin runtime scope required')

    def read(self,occurrence_id):
        self._scope();occurrence_id=UUID(str(occurrence_id))
        row=self.tx.execute('''SELECT p.*,o.source_event_id AS original_event,o.trigger_source
            FROM ecommerce_product_event_origin p JOIN automation_occurrence o USING(org_id,project_id,occurrence_id)
            WHERE p.org_id=%s AND p.project_id=%s AND p.occurrence_id=%s''',(*self.scope.key,occurrence_id)).fetchone()
        if row is None:return None
        body=dict(orgId=self.scope.org_id,projectId=self.scope.project_id,occurrenceId=str(occurrence_id),
                  sourceEventId=row['source_event_id'],runId=row['run_id'],actor=row['actor'])
        if row['trigger_source']!='event' or row['original_event']!=body['sourceEventId'] or canonical_sha256(body)!=row['content_hash']:
            raise ValueError('original event origin differs')
        return body

    def put(self,occurrence_id,*,event_key,run_id,actor,replayed):
        self._scope();occurrence_id=UUID(str(occurrence_id))
        if type(event_key) is not str or re.fullmatch('[0-9a-f]{64}',event_key) is None or type(replayed) is not bool:
            raise ValueError('canonical original event identity required')
        for value,bound in [(run_id,200),(actor,240)]:
            if type(value) is not str or not 1<=len(value)<=bound or value!=value.strip() or not value.isprintable():
                raise ValueError('canonical original batch and actor required')
        existing=self.read(occurrence_id)
        if existing is not None:
            if existing['sourceEventId']!=event_key:raise ValueError('original event origin drifted')
            return existing
        if replayed:raise ValueError('existing occurrence has no original batch origin')
        body=dict(orgId=self.scope.org_id,projectId=self.scope.project_id,occurrenceId=str(occurrence_id),
                  sourceEventId=event_key,runId=run_id,actor=actor)
        self.tx.execute('''INSERT INTO ecommerce_product_event_origin(org_id,project_id,occurrence_id,
            source_event_id,run_id,actor,content_hash) VALUES(%s,%s,%s,%s,%s,%s,%s)''',
            (*self.scope.key,occurrence_id,event_key,run_id,actor,canonical_sha256(body)))
        if self.read(occurrence_id)!=body:raise ValueError('original event origin readback differs')
        return body
