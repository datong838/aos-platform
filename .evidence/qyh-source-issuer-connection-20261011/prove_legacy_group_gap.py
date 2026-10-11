"""Actual before/after identity counterexample, confined to the isolated PG lab."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[2]
os.environ['AOS_DOTENV_DISABLED']='1'
sys.path.insert(0,str(ROOT/'services/aos-api'))
import psycopg
from psycopg import sql, IsolationLevel
from psycopg.rows import dict_row
from aos_api import aip_bi_plan_issuer_connection as current

if __name__=='__main__':
    result=Path(__file__).with_name('legacy-group-gap.json')
    assert not result.exists(), 'Reconcile existing probe'
    spec=importlib.util.spec_from_file_location('source_case',ROOT/'services/aos-api/tests/aip/test_aip_source_issuer_connection_pg.py')
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    source=subprocess.check_output(['git','show','f43d8682a:services/aos-api/aos_api/aip_bi_plan_issuer_connection.py'],cwd=ROOT,text=True)
    old=types.ModuleType('legacy_bi_connection');sys.modules[old.__name__]=old
    exec(compile(source,'original-committed-bi-connection','exec'),old.__dict__)
    with tempfile.TemporaryDirectory() as directory:
        generator=fixture.issuer_case.__wrapped__(Path(directory))
        configs,schema,admin=next(generator)
        group='source_gap_'+uuid4().hex[:12]
        try:
            admin.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(group)))
            admin.execute(sql.SQL('GRANT {} TO aos_bi_plan_issuer').format(sql.Identifier(group)))
            config=configs['plan'].database
            with psycopg.connect(host=config.host,port=config.port,user='aos_bi_plan_issuer',dbname=config.database,
                passfile=str(config.passfile),options=current._TIMEOUT_OPTIONS,row_factory=dict_row) as conn:
                conn.isolation_level=IsolationLevel.SERIALIZABLE
                conn.read_only=False
                current._bind_scope(conn,fixture.SCOPE)
                old._require_identity(conn,config,fixture.SCOPE,read_only=False)
                try:
                    current._require_identity(conn,config,fixture.SCOPE,read_only=False)
                except current.BIIssuerDatabaseBlocked:
                    rejected=True
                else:
                    rejected=False
                assert rejected
        finally:
            admin.execute(sql.SQL('DROP ROLE IF EXISTS {}').format(sql.Identifier(group)))
            generator.close()
    with result.open('x') as stream:
        json.dump({'originalCommittedIdentityAcceptedOtherGroup':True,'newIdentityRejectedSameConnection':True,
            'fixedLogin':'aos_bi_plan_issuer','runtimeMember':False,'ownerMember':False,
            'isolatedPort':18432,'currentDatabaseWrites':0,'formalIssuerAccepted':False},stream,indent=2)
    print('ACTUAL_LEGACY_GROUP_GAP_REPRODUCED_AND_CLOSED')
