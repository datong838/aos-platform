import hashlib,importlib.util,json,os,re,subprocess,sys
from pathlib import Path
from pglast.parser import parse_sql_json
R=Path(__file__).resolve().parent
old=R.parent/'qyh-org-name-maintenance-20261011'/'prepare.py'
s=importlib.util.spec_from_file_location('restore_tools',old);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
m.R=R;m.DB='aos_meta_head';m.SOURCE='aos-qyh-history-restore-20261011';TARGET='aos-qyh-history159-prepared-20261011'
private=R/'private';private.mkdir(exist_ok=True,mode=0o700);os.chmod(private,0o700)
target=json.loads(m.run(['docker','--context',m.CTX,'inspect','--format','{"id":{{json .Id}},"image":{{json .Image}},"network":{{json .HostConfig.NetworkMode}},"ports":{{json .HostConfig.PortBindings}},"mounts":{{json .Mounts}}}',TARGET]))
assert target['id']==json.loads((R/'created.json').read_text())['containerId'] and target['image']==m.IMAGE and target['network']=='none' and target['ports']=={} and len(target['mounts'])==1 and target['mounts'][0]['Name']=='aos-qyh-history159-prepared-data-20261011'
def read(container,sql):return json.loads(m.psql(container,m.DB,'BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; '+sql+'; COMMIT;'))
role_sql="""SELECT json_build_object('roles',(SELECT json_agg(json_build_object('name',rolname,'super',rolsuper,'inherit',rolinherit,'createRole',rolcreaterole,'createDb',rolcreatedb,'login',rolcanlogin,'replication',rolreplication,'bypassRls',rolbypassrls,'connectionLimit',rolconnlimit,'validUntil',rolvaliduntil,'settings',rolconfig) ORDER BY rolname) FROM pg_roles),'membership',(SELECT json_agg(json_build_object('role',r.rolname,'member',u.rolname,'grantor',g.rolname,'admin',x.admin_option,'inherit',x.inherit_option,'set',x.set_option) ORDER BY r.rolname,u.rolname,g.rolname) FROM pg_auth_members x JOIN pg_roles r ON r.oid=x.roleid JOIN pg_roles u ON u.oid=x.member JOIN pg_roles g ON g.oid=x.grantor),'database',(SELECT json_build_object('encoding',encoding,'localeProvider',datlocprovider,'collate',datcollate,'ctype',datctype,'icuLocale',daticulocale,'owner',datdba::regrole::text,'acl',(SELECT json_agg(a::text ORDER BY a::text) FROM unnest(datacl) a)) FROM pg_database WHERE datname=current_database()))"""
a=read(m.SOURCE,role_sql);b=read(TARGET,role_sql)
assert a['roles']==b['roles'] and a['membership']==b['membership']
m.record('catalog-before.json',{'source':a,'target':b,'passwordsExcluded':True})
expected=['=Tc/aos_app','aos_app=CTc/aos_app','aos_configuration_stage_transport_20260914=c/aos_app','aos_ui_read_transport_20260913=c/aos_app']
assert a['database']['acl']==sorted(expected)
if b['database']['acl']!=a['database']['acl']:
    assert b['database']['acl'] is None
    if (R/'acl-intent.json').exists():raise RuntimeError('Reconcile ACL attempt before replay')
    m.record('acl-intent.json',{'target':target,'database':m.DB,'onlyChange':'two original transport CONNECT grants','sourceWrites':False})
    m.psql(TARGET,m.DB,'BEGIN; GRANT CONNECT ON DATABASE aos_meta_head TO aos_ui_read_transport_20260913,aos_configuration_stage_transport_20260914; COMMIT;')
b=read(TARGET,role_sql);assert a==b
m.record('catalog-after.json',{'roleMembershipDatabaseExact':True,'source':a,'target':b,'passwordsExcluded':True})
def norm(node):
    if isinstance(node,list):return [norm(v) for v in node]
    if not isinstance(node,dict):return node
    value={k:norm(v) for k,v in node.items() if k not in {'location','stmt_location','stmt_len'}}
    if value.get('BoolExpr',{}).get('boolop')=='AND_EXPR':
        out=[]
        for arg in value['BoolExpr']['args']:
            if isinstance(arg,dict) and arg.get('BoolExpr',{}).get('boolop')=='AND_EXPR':out.extend(arg['BoolExpr']['args'])
            else:out.append(arg)
        value['BoolExpr']['args']=out
    return value
schemas=[]
for container,label in [(m.SOURCE,'source'),(TARGET,'target')]:
    raw=m.run(['docker','--context',m.CTX,'exec',container,'pg_dump','-U','aos_app','-d',m.DB,'--schema-only'])
    path=private/(label+'.sql');path.write_bytes(raw);os.chmod(path,0o600)
    lines=[line for line in raw.decode().rstrip().splitlines() if not line.startswith(('\\restrict ','\\unrestrict '))]
    schemas.append(lines)
assert len(schemas[0])==len(schemas[1])
differences=[]
for x,y in zip(*schemas):
    if x==y:continue
    px=re.fullmatch(r'\s*CONSTRAINT (\S+) CHECK (.+?)(,?)',x);py=re.fullmatch(r'\s*CONSTRAINT (\S+) CHECK (.+?)(,?)',y)
    assert px and py and px[1]==py[1] and px[3]==py[3],'Unreviewed schema difference'
    left=json.loads(parse_sql_json('CREATE TABLE x (v text, CONSTRAINT '+px[1]+' CHECK '+px[2]+');'))
    right=json.loads(parse_sql_json('CREATE TABLE x (v text, CONSTRAINT '+py[1]+' CHECK '+py[2]+');'))
    assert norm(left)==norm(right),'Check differs beyond regrouping'
    differences.append(px[1])
def sequences(container):
    params=read(container,"SELECT coalesce(json_agg(row_to_json(s) ORDER BY schemaname,sequencename),'[]') FROM pg_sequences s")
    quote=lambda v:'"'+v.replace('"','""')+'"'
    for item in params:
        state=read(container,'SELECT row_to_json(s) FROM (SELECT last_value,is_called FROM '+quote(item['schemaname'])+'.'+quote(item['sequencename'])+') s')
        item['state']=state
    return params
seq_a=sequences(m.SOURCE);seq_b=sequences(TARGET);assert seq_a==seq_b
m.record('sequence-comparison.json',{'count':len(seq_a),'source':seq_a,'target':seq_b,'equal':True})
before=json.loads((R/'source159-before.json').read_text())
assert m.fingerprint(m.SOURCE)==before and m.fingerprint(TARGET)==before
m.record('catalog-result.json',{'outcome':'DURABLE159_FULL_CATALOG_AND_DATA_VERIFIED','schemaLines':len(schemas[0]),'schemaHashes':[hashlib.sha256('\n'.join(x).encode()).hexdigest() for x in schemas],'andRegroupConstraints':differences,'normalization':'restrict token removal; locations and adjacentAND original order only','parserGrammar':180004,'rolesMembershipDatabaseAclExact':True,'sequences':len(seq_a),'sequenceParametersAndLastValueAndIsCalledExact':True,'tablesPreserved':len(before),'sourceWrites':False,'passwordRestoreProven':False,'migrationOrBusinessAcceptance':False})
print(json.dumps({'outcome':'DURABLE159_FULL_CATALOG_AND_DATA_VERIFIED','tables':len(before),'sequences':len(seq_a),'schemaAndRegroup':len(differences),'sourceWrites':False}))
