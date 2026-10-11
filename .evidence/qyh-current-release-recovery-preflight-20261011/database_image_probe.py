import hashlib,importlib.util,json,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('tools',R.parent/'qyh-org-name-maintenance-20261011'/'prepare.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
TARGET='aos-qyh-history159-prepared-20261011';DB='aos_meta_head'
identity=json.loads(m.psql(TARGET,DB,"BEGIN READ ONLY; SELECT json_build_object('cluster',(SELECT system_identifier::text FROM pg_control_system()),'version',(SELECT version_num FROM alembic_version)); COMMIT;"));assert identity=={'cluster':'7695302940039200809','version':'a0v_159'}
items=json.loads((R/'signed-readback.json').read_text())['items'];rows=[]
buildImages=json.loads((R.parents[2]/'aos-recovery/.aos-growth-113-build-receipt-20261002-r2.json').read_text())['images']
for entry in items:
 bundle,version=entry['bundle'],entry['version'];assert "'" not in bundle+version
 sql="BEGIN READ ONLY; SELECT coalesce(json_agg(row_to_json(x)),'[]'::json) FROM (SELECT v.version,v.content_hash,v.status FROM public.asset_bundle b JOIN public.asset_bundle_version v ON v.bundle_pk=b.bundle_pk WHERE b.publisher='aos' AND b.bundle_id='"+bundle+"' AND v.version='"+version+"') x; COMMIT;"
 registry=json.loads(m.psql(TARGET,DB,sql));row={'bundle':bundle,'version':version,'registry':registry,'registryExact':len(registry)==1 and registry[0]['content_hash']==entry['contentHash']}
 package='bundle-'+hashlib.sha256(json.dumps({'publisher':'aos','id':bundle},sort_keys=True,separators=(',',':')).encode()).hexdigest()
 schema=[]
 for requirement in entry.get('artifacts/schema-requirements.json',{}).get('requirements',[]):
  assert "'" not in requirement['version']
  found=json.loads(m.psql(TARGET,DB,"BEGIN READ ONLY; SELECT coalesce(json_agg(row_to_json(x)),'[]'::json) FROM (SELECT migration_hash FROM public.extension_schema_installation WHERE package_id='"+package+"' AND schema_version='"+requirement['version']+"') x; COMMIT;"))
  schema.append({'packageId':package,'required':requirement,'registered':found,'exact':len(found)==1 and found[0]['migration_hash']==requirement['migrationHash']})
 relations=[]
 for name in entry.get('artifacts/schema-compatibility.json',{}).get('requiredRelations',[]):
  assert "'" not in name
  exists=m.psql(TARGET,DB,"BEGIN READ ONLY; SELECT to_regclass('"+name+"') IS NOT NULL; COMMIT;")=='t';relations.append({'relation':name,'exists':exists})
 row.update({'schemaReceipts':schema,'requiredRelations':relations,'imagePresence':[]})
 for image in entry.get('artifacts/runtime-image-index.json',{}).get('images',[]):
  record=buildImages[bundle.replace('.','-')];assert record['imageDigest']==image['imageDigest'] and record['configDigest']==image['configDigest']
  p=subprocess.run(['docker','--context',m.CTX,'image','inspect',record['localRef'],'--format','{{.Id}}'],capture_output=True,text=True,timeout=10)
  row['imagePresence'].append({'imageDigest':image['imageDigest'],'localRef':record['localRef'],'expectedConfigDigest':image['configDigest'],'inspectExit':p.returncode,'localConfigDigest':p.stdout.strip() if p.returncode==0 else None,'exact':p.returncode==0 and p.stdout.strip()==image['configDigest']})
 rows.append(row)
(R/'database-image-readback.json').write_text(json.dumps({'identity':identity,'items':rows,'effects':0,'registryPublished':False,'schemaReceiptsCreated':False,'imagesPulledOrStarted':False},ensure_ascii=False,indent=2))
print(json.dumps([{'bundle':r['bundle'],'registryExact':r['registryExact'],'schemaExact':[s['exact'] for s in r['schemaReceipts']],'relationsExist':all(s['exists'] for s in r['requiredRelations']),'imagesExact':[s['exact'] for s in r['imagePresence']]} for r in rows]))
