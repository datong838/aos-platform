"""Execute original fixed-endpoint proof tests, adapting only fixture location."""
import ast
import hashlib
import json
import os
from pathlib import Path
import sys

import psycopg
from psycopg.conninfo import conninfo_to_dict
import pytest

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).parent
TEST=ROOT/'services/aos-api/tests/aip/test_aip_eval_report_proof_reader.py'
before=hashlib.sha256(TEST.read_bytes()).hexdigest()
assert os.environ['AOS_DATABASE_URL']=='postgresql://aos_app@127.0.0.1:18431/postgres'
with psycopg.connect(os.environ['AOS_DATABASE_URL']) as conn:
    assert str(conn.execute('SELECT system_identifier FROM pg_control_system()').fetchone()[0])=='7695416748450308141'
changes=[]


class Adapter:
    @pytest.hookimpl(tryfirst=True)
    def pytest_fixture_setup(self, fixturedef, request):
        if fixturedef.argname!='connection' or fixturedef.func.__module__!='test_aip_eval_report_proof_reader':
            return None
        parts=conninfo_to_dict(os.environ['AOS_DATABASE_URL'])
        assert parts['port']=='18431' and parts['dbname'].startswith('aos_test_') and parts['dbname'].endswith('_ti4_test')
        os.environ['AOS_BG00AF_TEST_DATABASE_URL']=os.environ['AOS_DATABASE_URL']
        module=ast.parse(TEST.read_text(encoding='utf-8-sig'))
        function=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='connection')
        function.decorator_list=[]
        class Endpoint(ast.NodeTransformer):
            replaced=0
            def visit_Constant(self,node):
                if node.value=='aos_bg00ad_schema_v2_20260929':
                    self.replaced+=1;return ast.copy_location(ast.Constant(parts['dbname']),node)
                if type(node.value) is int and node.value==5433:
                    self.replaced+=1;return ast.copy_location(ast.Constant(18431),node)
                return node
        adapter=Endpoint(); function=adapter.visit(function);assert adapter.replaced==2
        namespace=dict(fixturedef.func.__globals__)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])),str(TEST),'exec'),namespace)
        fixturedef.func=namespace['connection']
        changes.append({'fixture':'connection','endpointConstantsAdapted':2,'testModuleSha256':before,'database':parts['dbname'],'port':18431})
        return None


if __name__=='__main__':
    assert not (OUT/'verification.json').exists()
    code=pytest.main([str(TEST),str(ROOT/'services/aos-api/tests/aip/test_aip_eval_report_persisted_assembly_pg.py'),
        str(ROOT/'services/aos-api/tests/aip/test_aip_skill_binding_readiness_service.py'),
        str(ROOT/'services/aos-api/tests/aip/test_qyh_skill_proof_snapshot_pg.py'),'-q'],plugins=[Adapter()])
    after=hashlib.sha256(TEST.read_bytes()).hexdigest();assert before==after
    with (OUT/'verification.json').open('x') as stream:
        json.dump({'pytestExit':int(code),'originalTestSha256Before':before,'originalTestSha256After':after,
            'originalTestsByteUnchanged':True,'endpointOnlyAdaptations':changes,
            'historical5433Connected':False,'currentDatabaseChanged':False,'formalSourceAuthorityAccepted':False},stream,indent=2)
    raise SystemExit(code)
