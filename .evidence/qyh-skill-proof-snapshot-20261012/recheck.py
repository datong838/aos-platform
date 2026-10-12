"""Recheck original reports in their required snapshot, without altering evidence."""
import importlib.util
import json
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg import IsolationLevel
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('detail', ROOT/'.evidence/qyh-binding-currentness-detail-20261012/audit.py')
detail = importlib.util.module_from_spec(spec); spec.loader.exec_module(detail)
from aos_api.aip_release_publication_service import AipReleasePublicationService, AipReleasePublicationError
from aos_api.aip_eval_execution_authority import EvalExecutionRejected


@contextmanager
def snapshot(scope):
    with psycopg.connect(host='127.0.0.1',port=18431,dbname='qyh_source_contract_20261011',
                         user='qyh_restored_api_login',row_factory=dict_row) as conn:
        conn.isolation_level=IsolationLevel.REPEATABLE_READ
        conn.read_only=True
        conn.execute('SET LOCAL ROLE aos_runtime')
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope.key)
        assert conn.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']=='7695416748450308141'
        yield conn


def observe():
    registry=detail.AipSkillRegistry(snapshot)
    rows=[]
    for item in json.loads((detail.OUT/'current.json').read_text())['rows']:
        binding=registry.get_binding(detail.SCOPE,item['bindingId'])
        with snapshot(detail.SCOPE) as conn:
            row=conn.execute('SELECT * FROM aip_release_gate_decision WHERE org_id=%s AND project_id=%s AND decision_id=%s',
                (*detail.SCOPE.key,binding.dependencies.eval_gate_ref.asset_id)).fetchone()
            gate=AipReleasePublicationService._gate_from_row(detail.SCOPE,row)
            try:
                AipReleasePublicationService._verify_gate_evidence(conn,detail.SCOPE,gate)
            except AipReleasePublicationError as error:
                chain=[]; cause=error
                while cause is not None:
                    chain.append({'type':type(cause).__name__,
                        'reason':str(cause) if isinstance(cause,(AipReleasePublicationError,EvalExecutionRejected)) else None,
                        'sqlstate':getattr(cause,'sqlstate',None)})
                    cause=cause.__cause__
                result={'verified':False,'chain':chain}
            else:
                result={'verified':True}
        rows.append({'bindingId':binding.binding_id,'result':result})
    return rows


if __name__=='__main__':
    path=Path(__file__).parent/'repeatable-recheck.json'; assert not path.exists()
    first,second=observe(),observe(); assert first==second
    with path.open('x') as stream: json.dump({'rows':first,'twoViewsEqual':True,'readOnly':True,'isolation':'repeatable read'},stream,indent=2)
    print(json.dumps({'verified':sum(r['result']['verified'] for r in first),
        'causePatterns':list({json.dumps(r['result'],sort_keys=True) for r in first})}))
