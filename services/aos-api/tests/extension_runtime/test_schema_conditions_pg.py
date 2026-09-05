from datetime import datetime,timezone
import json
import os
from types import SimpleNamespace

import pytest

from test_lifecycle_pg import database
from test_admission import fixture

pytestmark=pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST')!='1',reason='isolated PG opt-in')


@pytest.mark.parametrize('case',['valid','missing','wrong_hash','wrong_version','wrong_publisher','legacy_id'])
def test_signed_conditions_read_exact_shared_schema(database,case):
    from aos_api.extension_runtime.schema_conditions import CurrentSchemaConditions,schema_package_id
    from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
    conn,_,_=database
    def files(items):
        items['artifacts/schema-requirements.json']=json.dumps({'schemaVersion':1,'requirements':[
            {'version':'1','migrationHash':'sha256:'+'e'*64}]}).encode()
    args,_=fixture(files,now=datetime.now(timezone.utc))
    selected=args['selected']
    if case!='missing':
        conn.execute('INSERT INTO extension_schema_installation(package_id,schema_version,migration_hash) VALUES(%s,%s,%s)',
            (selected.id if case=='legacy_id' else schema_package_id('another-publisher' if case=='wrong_publisher' else selected.publisher,selected.id),
             '2' if case=='wrong_version' else '1','sha256:'+('f' if case=='wrong_hash' else 'e')*64))
    reader=CurrentSchemaConditions(load_record=lambda s:args['record'],
        read_artifact=lambda s,path,limit:args['read_artifact'](path,limit),policy=args['policy'])
    with conn.transaction():
        kwargs=dict(conn=conn,locked=None,lock=SimpleNamespace(payload=SimpleNamespace(resolved=[selected])),actor='test')
        if case=='valid':assert reader(**kwargs) is True
        else:
            with pytest.raises((LookupError,RuntimeConflict)):reader(**kwargs)
