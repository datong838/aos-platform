"""Same original table fingerprints, serial queries in one readonly snapshot."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
CONTEXT = 'colima-aos-extension'
SOURCE = 'qyh-restored-pg-20261011'


def command(*args, **kwargs):
    return subprocess.run(['docker','--context',CONTEXT,*args],
                          check=True,timeout=60,**kwargs)


if __name__ == '__main__':
    source = json.loads(command('inspect',SOURCE,capture_output=True,text=True).stdout)[0]
    assert source['Id']=='84989681fb7d3fc0f42d750672547ca0208fbba08dfef0d93837d8e64245dc3c'
    assert source['State']['Running'] and len(source['Mounts'])==1
    assert source['Mounts'][0]['Name']=='aos-qyh-history159-prepared-data-20261011'
    memory = command('exec',SOURCE,'cat','/proc/meminfo',capture_output=True,text=True).stdout
    available = int(next(line for line in memory.splitlines() if line.startswith('MemAvailable:')).split()[1])
    assert available>=256*1024, 'Insufficient measured margin: no fingerprint query started'
    spec = importlib.util.spec_from_file_location('readonly_backup', ROOT /
        '.evidence/qyh-current159-fresh-backup-restore-20261012/backup_restore.py')
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    current = json.loads(reader.current_sql("""SELECT json_build_object(
        'cluster',(SELECT system_identifier::text FROM pg_control_system()),
        'schema',(SELECT version_num FROM alembic_version));"""))
    assert current=={'cluster':'7695302940039200809','schema':'a0v_161'}
    inventory = "SELECT json_agg(json_build_object('schema',n.nspname,'name',c.relname) ORDER BY n.nspname,c.relname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='r' AND n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%';"
    tables = json.loads(reader.current_sql(inventory))
    assert len(tables)==650
    queries = ["BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;",
               "SET LOCAL work_mem='1MB';", "SET LOCAL max_parallel_workers_per_gather=0;",
               "SET LOCAL statement_timeout='5s';", inventory]
    for table in tables:
        qualified = '.'.join('"'+table[k].replace('"','""')+'"' for k in ('schema','name'))
        key = (table['schema']+'.'+table['name']).replace("'","''")
        queries.append("SELECT row_to_json(x) FROM (SELECT '"+key+"' AS name,count(*) AS rows,encode(sha256(convert_to(coalesce(string_agg(h,'' ORDER BY h),''),'UTF8')),'hex') AS hash FROM (SELECT encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex') AS h FROM "+qualified+" t) q)x;")
    queries.append('COMMIT;')
    with (OUT/'bounded-fingerprint-intent-20261013.json').open('x') as f:
        json.dump({'source':source['Id'],'native':current,'memoryAvailableKB':available,
            'queries':650,'serial':True,'repeatableRead':True,'readOnly':True,
            'workMem':'1MB','maxParallelWorkersPerGather':0,'perStatementTimeoutSeconds':5},f,indent=2)
    result = command('exec','-i',SOURCE,'psql','-X','-qAt','-v','ON_ERROR_STOP=1',
                     '-U','aos_app','-d','aos_meta_head',input='\n'.join(queries),
                     capture_output=True,text=True)
    assert not result.stderr.strip()
    lines = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    assert lines[0]==tables and len(lines)==651
    rows = lines[1:]
    fingerprints = {r['name']:{'rows':r['rows'],'hash':r['hash']} for r in rows}
    assert len(fingerprints)==650
    assert all(type(v['rows']) is int and v['rows']>=0 and len(v['hash'])==64
               for v in fingerprints.values())
    with (OUT/'bounded-fingerprint-current-20261013.json').open('x') as f:
        json.dump({'outcome':'CURRENT_650_TABLE_READONLY_SERIAL_SNAPSHOT_GREEN',
            'native':current,'sourceContainer':source['Id'],
            'fingerprints':fingerprints,'currentDatabaseWrites':False,
            'historicalComparisonProven':False,'fullRestoreRehearsalAccepted':False,
            'scriptSHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},f,indent=2)
    print('CURRENT_650_TABLE_READONLY_SERIAL_SNAPSHOT_GREEN')
