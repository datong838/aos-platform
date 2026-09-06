"""Trusted synchronous composition of signed admission, epoch gate and read port."""
from .admission import admit_query_registry
from .lifecycle_store import _require_transaction,_values
from .runtime_gate import run_guarded,_reject_deferred
from .storage_ports import read_registered_rows


class SignedQueryBroker:
    """Internal host seam; it exposes neither arbitrary SQL nor a reusable permit."""
    def __init__(self,*,query_connect,installation_store,load_record,read_artifact,
                 release_policy,check_current_policy):
        values=(query_connect,load_record,read_artifact,check_current_policy)
        if not all(callable(value) for value in values) or installation_store is None or release_policy is None:
            raise ValueError('trusted signed query dependencies required')
        self.query_connect=query_connect
        self.installation_store=installation_store
        self.load_record=load_record
        self.read_artifact=read_artifact
        self.release_policy=release_policy
        self.check_current_policy=check_current_policy

    def dispatch(self,conn,*,org_id,project_id,current_ref,generation,request_epoch,
                 selected,operation_id,parameter):
        _require_transaction(conn)
        if type(operation_id) is not str or not operation_id:
            raise ValueError('exact query operation required')
        def execute():
            record=self.load_record(selected)
            _reject_deferred(record)
            checked_at=_values(conn.execute('SELECT clock_timestamp() AS now').fetchone(),('now',))[0]
            admitted=admit_query_registry(record=record,selected=selected,policy=self.release_policy,
                checked_at=checked_at,read_artifact=lambda path,limit:self.read_artifact(selected,path,limit))
            matches=[definition for definition in admitted if definition.operation_id==operation_id]
            if len(matches)!=1:
                raise LookupError('signed query operation unavailable')
            definition=matches[0]
            opened=self.query_connect()
            _reject_deferred(opened)
            with opened as query_conn:
                return read_registered_rows(query_conn,raw=definition.raw,
                    expected_hash=definition.expected_hash,table=definition.table,
                    column_types=dict(definition.column_types),parameter=parameter,
                    org_id=org_id,project_id=project_id,limit=definition.limit)
        return run_guarded(conn,installation_store=self.installation_store,
            org_id=org_id,project_id=project_id,current_ref=current_ref,generation=generation,
            request_epoch=request_epoch,selected=selected,
            check_current_policy=self.check_current_policy,execute=execute)
