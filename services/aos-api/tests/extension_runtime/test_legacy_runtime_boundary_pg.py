from psycopg.types.json import Jsonb
import pytest
from test_lifecycle_pg import database, pytestmark

from aos_api.asset_registry.legacy_runtime_boundary import legacy_content_predicate


def test_complete_lock_legacy_eligibility_on_postgres(database):
    conn, _, _ = database
    conn.execute('CREATE TABLE asset_bundle(bundle_pk int PRIMARY KEY,publisher text,bundle_id text)')
    conn.execute('CREATE TABLE asset_bundle_version(version_pk int PRIMARY KEY,bundle_pk int,version text,content_hash text,manifest_json jsonb)')
    conn.execute("INSERT INTO asset_bundle VALUES(1,'aos','content'),(2,'aos','runtime')")
    conn.execute("INSERT INTO asset_bundle_version VALUES(1,1,'1','hash-content',%s),(2,2,'1','hash-runtime',%s)",
        (Jsonb({'spec':{'runtime':None}}),Jsonb({'spec':{'runtime':{'backend':{}}}})))
    content={'publisher':'aos','id':'content','version':'1','contentHash':'hash-content'}
    runtime={'publisher':'aos','id':'runtime','version':'1','contentHash':'hash-runtime'}
    for alias in ('l','bil','composition_lock'):
        for resolved,expected in (([content],True),([runtime],False),([content,runtime],False),
            ([{**content,'contentHash':'wrong'}],False),([{**content,'version':'missing'}],False),
            ([{}],False),([],False),({},False),(None,False)):
            value=conn.execute(f'SELECT {legacy_content_predicate(alias)} FROM (SELECT %s::jsonb AS lock_payload) {alias}',
                (Jsonb({'resolved':resolved}),)).fetchone()[0]
            assert value is expected
    conn.execute("UPDATE asset_bundle_version SET manifest_json='{}'::jsonb WHERE version_pk=1")
    assert conn.execute(f'SELECT {legacy_content_predicate("l")} FROM (SELECT %s::jsonb AS lock_payload) l',
        (Jsonb({'resolved':[content]}),)).fetchone()[0] is False


@pytest.mark.parametrize('alias', ['l; DROP TABLE x','request','',None])
def test_alias_is_only_a_fixed_host_identifier(alias):
    with pytest.raises(ValueError):legacy_content_predicate(alias)
