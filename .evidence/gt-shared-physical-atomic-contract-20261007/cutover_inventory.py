"""Read-only exact legacy mappings; no import, release, or business authority."""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

base=Path(__file__).resolve().parent
repo=base.parents[1]
sys.path.insert(0,str(repo/'services/aos-api'))
from aos_api.aip_provider_capacity_publication_contracts import PublishedProviderCapacitySourceV2,parse_signed_capacity_body
passfile=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode&0o077==0
for key in ('PGPASSWORD','PGPASSFILE','PGOPTIONS','PGSERVICE','PGSERVICEFILE'):
    os.environ.pop(key,None)
inputs=['source-pool-counterexample.json','fixed-window-counterexample.json','legacy-ttl-r2.json']
records={name:json.loads((base/name).read_text()) for name in inputs}
expected={'aos_test_b6bde5fde605_ti4_test','aos_test_1c592b9c2334_ti4_test','aos_test_legacy_ttl_f65022995fae'}
assert {r['database'] for r in records.values()}==expected
observations={}
for record in records.values():
    database=record['database']
    with psycopg.connect(host='127.0.0.1',port=5434,user='aos_app',dbname=database,
        passfile=str(passfile),row_factory=dict_row) as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert str(c.execute('SELECT system_identifier FROM pg_control_system()').fetchone()['system_identifier'])=='7693564235776004128'
        sources=c.execute("""SELECT s.account_id,s.content_hash,s.source_raw,
            aos_ed25519.verify(s.signature,s.source_raw,decode(p.original_signed_facts->>'sourceSignerPublicKey','base64')) AS signature_valid
            FROM aos_capacity_publication_private.source_publication s
            JOIN aos_capacity_publication_private.source_provenance p USING(org_id,project_id,asset_id)""").fetchall()
        parsed=[]
        for s in sources:
            assert s['signature_valid'] and hashlib.sha256(bytes(s['source_raw'])).hexdigest()==s['content_hash']
            source=parse_signed_capacity_body(bytes(s['source_raw']),PublishedProviderCapacitySourceV2)
            assert str(s['account_id'])==str(source.physical_account_id)
            parsed.append((s['content_hash'],source))
        rows=c.execute("""SELECT r.reservation_id,r.status,r.agent_run_id,r.request_units,r.token_units,
            r.expires_at<=clock_timestamp() AS clock_expired,p.provider_id,p.provider_revision,p.provider_hash,
            m.account_id,m.org_id AS mapping_org,m.project_id AS mapping_project,
            EXISTS(SELECT 1 FROM aip_agent_run a WHERE a.org_id=r.org_id AND a.project_id=r.project_id
                AND a.agent_run_id=r.agent_run_id) AS agent_run_exists,
            r.org_id,r.project_id
            FROM aip_model_capacity_reservation r
            JOIN aip_model_capacity_pool_revision p ON p.org_id=r.org_id AND p.project_id=r.project_id
                AND p.pool_id=r.pool_id AND p.revision=r.pool_revision
            LEFT JOIN aos_capacity_publication_private.global_provider m ON m.provider_id=p.provider_id
            ORDER BY r.reservation_id""").fetchall()
        kept=[]
        for r in rows:
            assert (r['org_id'],r['project_id'])==('org-org','dev-project')
            matches=[h for h,s in parsed if str(s.physical_account_id)==str(r['account_id'])
                and any((p.asset_id,p.revision,p.content_hash)==(r['provider_id'],r['provider_revision'],r['provider_hash']) for p in s.provider_refs)]
            mapped=r['account_id'] is not None and (r['mapping_org'],r['mapping_project'])==('org-org','dev-project') and bool(matches)
            assert not r['agent_run_exists']
            kept.append(dict(reservation_id=r['reservation_id'],legacy_status=r['status'],clock_expired=r['clock_expired'],
                request_units=r['request_units'],token_units=r['token_units'],exact_signed_mapping=bool(mapped),
                physical_account_id=str(r['account_id']) if mapped else None,matching_source_hashes=matches,
                actual_agent_run_exists=False,zero_effect_proven=False,
                cutover_disposition='HOLD_FOR_PROVENANCE_RECONCILIATION' if mapped else 'UNMAPPED_BLOCK_NEW_ADMISSION'))
        assert c.execute("SELECT count(*) AS n FROM aip_model_capacity_reservation WHERE org_id='dev-org'").fetchone()['n']==0
        events=c.execute('SELECT event_type,count(*) AS n FROM aip_model_capacity_event GROUP BY event_type ORDER BY event_type').fetchall()
        observations[database]=dict(rows=kept,events=events,source_count=len(sources),canary=0)
assert len(observations['aos_test_b6bde5fde605_ti4_test']['rows'])==3
assert len(observations['aos_test_1c592b9c2334_ti4_test']['rows'])==2
assert all(r['exact_signed_mapping'] for name in expected if 'legacy_ttl' not in name for r in observations[name]['rows'])
legacy=observations['aos_test_legacy_ttl_f65022995fae']['rows']
assert len(legacy)==4 and all(not r['exact_signed_mapping'] for r in legacy)
assert sum(r['legacy_status']=='expired' for r in legacy)==2
result=dict(status='READ_ONLY_EXACT_LEGACY_MAPPING_INVENTORY',databases=observations,
    file_sha256={name:hashlib.sha256((base/name).read_bytes()).hexdigest() for name in inputs},
    limitations=['All rows are retained isolated counterexamples, not legitimate business unknown history',
        'No import or discharge performed; missing provenance remains a cutover requirement',
        'Historical signed mapping is not current Source admission or execution permission'])
(base/'cutover-inventory.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['status'],'5 exact signed history mappings,4 unmapped legacy rows;2 expired not zero-effect;AgentRun0/canary0')
