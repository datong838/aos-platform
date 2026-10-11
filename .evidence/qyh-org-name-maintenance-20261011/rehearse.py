# coding: utf-8
import importlib.util,sys,json,hashlib,subprocess,re
from pglast.parser import parse_sql_json
from pathlib import Path
R=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('qyh_prepare',R/'prepare.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
TARGET='aos-qyh-name-rehearsal-20261011-r3'
if (R/'rename-intent.json').exists():raise RuntimeError('Mutation intent exists; reconcile first')
assert json.loads((R/'r3-restore-result.json').read_text())['outcome']=='FULL_DATA_RESTORE_FINGERPRINT_EQUAL'
# Keep full SQL definitions private; publish digests only.
def schema(container,label):
 raw=m.run(['docker','--context',m.CTX,'exec',container,'pg_dump','-U','aos_app','-d',m.DB,'--schema-only'])
 (m.PRIVATE/(label+'-schema.sql')).write_bytes(raw)
 normalized=b'\n'.join(line for line in raw.splitlines() if not line.startswith((b'\\restrict ',b'\\unrestrict ')))
 return {'bytes':len(normalized),'sha256':hashlib.sha256(normalized).hexdigest()}
source_schema=schema(m.SOURCE,'source');target_schema=schema(TARGET,'restored')
def clean(label):
 text=(m.PRIVATE/(label+'-schema.sql')).read_text()
 return '\n'.join(x for x in text.splitlines() if not x.startswith(('\\restrict ','\\unrestrict '))).rstrip().splitlines()
def norm(node):
 if isinstance(node,list):return [norm(x) for x in node]
 if not isinstance(node,dict):return node
 value={k:norm(v) for k,v in node.items() if k not in {'location','stmt_location','stmt_len'}}
 if 'BoolExpr' in value and value['BoolExpr'].get('boolop')=='AND_EXPR':
  out=[]
  for arg in value['BoolExpr']['args']:
   if isinstance(arg,dict) and arg.get('BoolExpr',{}).get('boolop')=='AND_EXPR':out.extend(arg['BoolExpr']['args'])
   else:out.append(arg)
  value['BoolExpr']['args']=out
 return value
left,right=clean('source'),clean('restored');assert len(left)==len(right)
regroup=[]
for x,y in zip(left,right):
 if x==y:continue
 px=re.fullmatch(r'\s*CONSTRAINT (\S+) CHECK (.+?)(,?)',x);py=re.fullmatch(r'\s*CONSTRAINT (\S+) CHECK (.+?)(,?)',y)
 assert px and py and px[1]==py[1] and px[3]==py[3],'Unreviewed schema difference'
 ax=json.loads(parse_sql_json('CREATE TABLE x (v text, CONSTRAINT '+px[1]+' CHECK '+px[2]+');'))
 ay=json.loads(parse_sql_json('CREATE TABLE x (v text, CONSTRAINT '+py[1]+' CHECK '+py[2]+');'))
 assert norm(ax)==norm(ay),'Constraint expression differs beyond AND grouping/location'
 regroup.append(px[1])
m.record('schema-roundtrip-differences.json',{'constraints':regroup,'count':len(regroup),'parserVersion':180004,'normalization':'remove locations; flatten adjacent AND in original leaf order only','otherSchemaLinesExact':True,'rawDumpHashesEqual':False})
role_sql="""BEGIN READ ONLY; SELECT json_build_object('roles',(SELECT json_agg(json_build_object('name',rolname,'super',rolsuper,'inherit',rolinherit,'createRole',rolcreaterole,'createDb',rolcreatedb,'login',rolcanlogin,'replication',rolreplication,'bypassRls',rolbypassrls,'connectionLimit',rolconnlimit,'validUntil',rolvaliduntil,'settings',rolconfig) ORDER BY rolname) FROM pg_roles),'membership',(SELECT json_agg(json_build_object('role',r.rolname,'member',u.rolname,'grantor',g.rolname,'admin',x.admin_option,'inherit',x.inherit_option,'set',x.set_option) ORDER BY r.rolname,u.rolname,g.rolname) FROM pg_auth_members x JOIN pg_roles r ON r.oid=x.roleid JOIN pg_roles u ON u.oid=x.member JOIN pg_roles g ON g.oid=x.grantor),'database',(SELECT json_build_object('encoding',encoding,'localeProvider',datlocprovider,'collate',datcollate,'ctype',datctype,'icuLocale',daticulocale,'owner',datdba::regrole::text,'acl',(SELECT json_agg(a::text ORDER BY a::text) FROM unnest(datacl) a)) FROM pg_database WHERE datname=current_database())); COMMIT;"""
a=json.loads(m.psql(m.SOURCE,m.DB,role_sql));b=json.loads(m.psql(TARGET,m.DB,role_sql));assert a==b,'Role/membership/database attributes differ'
m.record('catalog-comparison.json',{'sourceSchema':source_schema,'targetSchema':target_schema,'reviewedAndRegroupConstraints':len(regroup),'roleAndMembershipAndDatabaseEqual':True,'rolePasswordsCompared':False,'sourceWrites':False})
new_name='\u6816\u6708\u6c47\u5546\u8d38\u6709\u9650\u516c\u53f8'
original=json.loads(m.psql(m.SOURCE,'aos_meta',"BEGIN READ ONLY; SELECT json_build_object('id',id,'name',name) FROM meta_org WHERE id='org-org'; COMMIT;"));assert original=={'id':'org-org','name':new_name}
old=json.loads(m.psql(TARGET,m.DB,"BEGIN READ ONLY; SELECT json_build_object('id',id,'name',name,'updatedAt',updated_at::text) FROM meta_org WHERE id='org-org'; COMMIT;"));assert old['name']=='org-org'
# Freeze the precise target values; no caller-selected target or installation mutation.
quote=lambda v:"'"+v.replace("'","''")+"'"
update="UPDATE ONLY public.meta_org SET name="+quote(new_name)+",updated_at=clock_timestamp() WHERE id='org-org' AND name='org-org' AND updated_at="+quote(old['updatedAt'])+"::timestamptz RETURNING id,name"
# Unexpected source name must not affect a row.
negative=m.psql(TARGET,m.DB,"BEGIN; WITH x AS (UPDATE ONLY public.meta_org SET name='unexpected' WHERE id='org-org' AND name='WRONG_EXPECTED_NAME' RETURNING id) SELECT count(*) FROM x; ROLLBACK;");assert negative=='0'
rollback=json.loads(m.psql(TARGET,m.DB,'BEGIN; WITH x AS ('+update+') SELECT row_to_json(x) FROM x; ROLLBACK;'));assert rollback==original
before=json.loads((R/'r3-restored-fingerprint.json').read_text());after_rollback=m.fingerprint(TARGET);assert before==after_rollback
m.record('rename-intent.json',{'target':TARGET,'database':m.DB,'table':'public.meta_org','row':old,'newName':new_name,'sourceWrites':False,'rollbackPassed':True,'negativeWrongNameAffectedRows':0})
committed=json.loads(m.psql(TARGET,m.DB,'BEGIN; WITH x AS ('+update+') SELECT row_to_json(x) FROM x; COMMIT;'));assert committed==original
post=m.fingerprint(TARGET);changes=[(x['table'],y['table']) for x,y in zip(before,post) if x!=y];assert changes==[('public.meta_org','public.meta_org')],changes
assert [x['rows'] for x in before]==[x['rows'] for x in post]
source_post=m.fingerprint(m.SOURCE);assert source_post==json.loads((R/'source-fingerprint-before.json').read_text())
assert m.psql(m.SOURCE,m.DB,"BEGIN READ ONLY; SELECT name FROM meta_org WHERE id='org-org'; COMMIT;")=='org-org'
m.record('name-rehearsal-result.json',{'outcome':'ISOLATED_NAME_CHANGE_ONLY_META_ORG','target':TARGET,'allTablesChecked':len(before),'changedTables':['public.meta_org'],'rowCountsUnchanged':True,'rollbackFingerprintExact':True,'negativeWrongNameAffectedRows':0,'sourceFingerprintUnchanged':True,'formalSourceRenamePerformed':False,'formalActivationPerformed':False})
(R/'proposed-name-update.sql').write_text('-- PROPOSAL ONLY. Current formal source remains READ ONLY.\n-- Source identity, backup and explicit formal maintenance gate must be revalidated.\nBEGIN;\n'+update+';\n-- Require exactly one returned row; otherwise rollback.\nCOMMIT;\n')
print(json.dumps({'outcome':'ISOLATED_NAME_CHANGE_ONLY_META_ORG','tables':len(before),'sourceWrites':False}))
