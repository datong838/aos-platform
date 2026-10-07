"""PostgreSQL AST of actual original Source helper calls; no function execution."""
import hashlib
import json
import re
import subprocess
from collections import deque
from pathlib import Path

import pglast

BASE=Path(__file__).resolve().parent
REPO=BASE.parents[1]
TARGET='test_occupation_source_consumption_uses_actual_business_caller'


def nodes(value, path=''):
    if isinstance(value,dict):
        yield path,value
        for key,item in value.items():
            yield from nodes(item,path+'/'+key)
    elif isinstance(value,(list,tuple)):
        for index,item in enumerate(value):
            yield from nodes(item,path+'/'+str(index))


def sql_summary(query):
    try:
        tree=pglast.parse_sql(query)
    except pglast.Error:
        tree=pglast.parse_sql('SELECT '+query)
    tree=[stmt(skip_none=True) for stmt in tree]
    calls=set();relations=set();locks=[];templates=[];operations=set()
    for _,node in nodes(tree):
        kind=node.get('@')
        if kind=='FuncCall':
            parts=[p['sval'] for p in node['funcname']]
            if len(parts)>1:calls.add('.'.join(parts))
            if parts[-1]=='format' and node.get('args'):
                first=node['args'][0]
                if first.get('@')=='A_Const' and first.get('val',{}).get('@')=='String':
                    templates.append(first['val']['sval'])
        if kind=='RangeVar':relations.add((node.get('schemaname','<search_path>'))+'.'+node['relname'])
        if kind=='LockingClause':
            locks.append(dict(strength=node['strength']['name'],
                relations=[r.get('relname') for r in node.get('lockedRels',[])],
                wait_policy=node['waitPolicy']['name']))
        if kind in ('SelectStmt','InsertStmt','UpdateStmt','DeleteStmt','MergeStmt'):
            operations.add(kind)
    return dict(calls=sorted(calls),relations=sorted(relations),locks=locks,
        operations=sorted(operations)),templates


def describe(function):
    result=dict(identity=function['identity'],language=function['language'],
        body_sha256=hashlib.sha256(function['body'].encode()).hexdigest(),expressions=[],
        parse_failures=[],dynamic_statements=[])
    if function['language'] not in ('plpgsql','sql'):
        result['opaque_non_SQL_language']=True
        return result
    try:
        if function['language']=='plpgsql':
            tree=pglast.parse_plpgsql(function['definition'])
            expressions=[(path,node['query'],node.get('parseMode')) for path,node in nodes(tree)
                if 'query' in node and isinstance(node['query'],str)]
        else:
            expressions=[('/SQL_function',function['body'],0)]
            tree=[]
    except pglast.Error as error:
        result['parse_failures'].append(dict(stage='PLpgSQL',error_type=type(error).__name__))
        return result
    summaries={}
    for path,query,mode in expressions:
        try:
            if mode==3:
                assignment=re.fullmatch(r'\s*[A-Za-z_]\w*\s*:=\s*(.*)',query,re.S)
                if not assignment:
                    raise pglast.Error('Unsupported fixed PLpgSQL assignment target')
                query=assignment.group(1)
            elif mode not in (0,2):
                raise pglast.Error('Unsupported PLpgSQL parseMode')
            summary,templates=sql_summary(query)
            summaries[path]=(summary,templates)
            if summary['calls'] or summary['relations'] or summary['locks'] or any(
                    x!='SelectStmt' for x in summary['operations']):
                result['expressions'].append(dict(control_flow_path=path,**summary))
        except pglast.Error as error:
            result['parse_failures'].append(dict(stage='embedded_SQL',control_flow_path=path,
                query_sha256=hashlib.sha256(query.encode()).hexdigest(),error_type=type(error).__name__))
    for path,node in nodes(tree):
        if 'PLpgSQL_stmt_dynexecute' not in node:
            continue
        dynamic=node['PLpgSQL_stmt_dynexecute'];query=dynamic['query']['PLpgSQL_expr']['query']
        entry=dict(control_flow_path=path,template_summaries=[],runtime_arguments_unresolved=True)
        try:
            _,templates=sql_summary(query)
            for template in templates:
                # Symbolic placeholders only: never execute or infer catalog variable values.
                symbolic=template.replace('%%','__literal_percent__')
                symbolic=re.sub(r'%(?:\d+\$)?[sIL]',lambda m: '$1' if m.group(0).endswith('s')
                    else 'symbolic_identifier' if m.group(0).endswith('I') else 'NULL',symbolic)
                summary,_=sql_summary(symbolic.replace('__literal_percent__','%'))
                entry['template_summaries'].append(dict(template_sha256=hashlib.sha256(template.encode()).hexdigest(),**summary))
            entry['constant_format_templates']=len(templates)
        except pglast.Error as error:
            entry['parse_error_type']=type(error).__name__
        result['dynamic_statements'].append(entry)
    return result


def probe(caller, source, command, sign, subject):
    from tests.aip.test_network_consumer_boundary_pg import isolated_owner
    from aos_api.aip_provider_capacity_occupation_source import occupation_source_statements
    expected={}
    for statement in occupation_source_statements():
        for match in re.finditer(r'CREATE(?: OR REPLACE)? FUNCTION\s+(public\.\w+)\([^)]*\).*?'
                r'AS\s+(\$\w*\$)(.*?)\2',statement,re.S):
            expected[match.group(1)]=hashlib.sha256(match.group(3).encode()).hexdigest()
    roots=['public.read_capacity_source_for_occupation','public.require_capacity_occupation_source_installation']
    assert set(expected)==set(roots)
    with isolated_owner() as admin:
        admin.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        identity=admin.execute("SELECT current_database() AS database,current_setting('transaction_read_only') AS readonly,"
            "system_identifier::text AS cluster FROM pg_control_system()").fetchone()
        assert identity['readonly']=='on' and identity['cluster']=='7693564235776004128'
        rows=admin.execute("""SELECT n.nspname||'.'||p.proname AS name,
            n.nspname||'.'||p.proname||'('||pg_get_function_identity_arguments(p.oid)||')' AS identity,
            l.lanname AS language,p.prosrc AS body,pg_get_functiondef(p.oid) AS definition
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            JOIN pg_language l ON l.oid=p.prolang
            WHERE p.prokind='f' AND (n.nspname='public' OR n.nspname='aos_ed25519'
                OR n.nspname LIKE 'aos_capacity_%private')""").fetchall()
        by_name={}
        for row in rows:by_name.setdefault(row['name'],[]).append(row)
        for root in roots:
            assert len(by_name.get(root,[]))==1
            assert hashlib.sha256(by_name[root][0]['body'].encode()).hexdigest()==expected[root]
        pending=deque(roots);seen=set();functions=[];unresolved=set();overloads={}
        while pending:
            name=pending.popleft()
            if name in seen:continue
            seen.add(name)
            candidates=by_name.get(name,[])
            if not candidates:
                if not name.startswith('pg_catalog.'):
                    unresolved.add(name)
                continue
            if len(candidates)>1:overloads[name]=len(candidates)
            for function in candidates:
                described=describe(function);functions.append(described)
                for expr in described['expressions']:
                    pending.extend(expr['calls'])
                for dynamic in described['dynamic_statements']:
                    for summary in dynamic['template_summaries']:
                        pending.extend(summary['calls'])
        assert all(admin.execute('SELECT count(*) AS n FROM '+table).fetchone()['n']==0
            for table in ('aip_agent_run','aip_model_capacity_reservation','aip_budget_reservation'))
        result=dict(status='ACTUAL_OCCUPATION_SOURCE_AST_HELPER_CLOSURE_OBSERVED',identity=identity,
            source_hash=command.source_ref.content_hash,physical_account_id=str(source.physical_account_id),
            trusted_root_bodies_match=True,functions=functions,unresolved_explicit_calls=sorted(unresolved),
            conservative_overload_candidates=overloads,
            parser_version=pglast.__version__,
            head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
            probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            limitations=['Private helper authenticity is enforced by original successful Source installation audit',
                'AST is a possible control-flow graph, not timing or whole-writer concurrency evidence',
                'Dynamic runtime identifiers and overload resolution remain explicit, not inferred',
                'Implicit FK/unique locks and non-SQL implementation require separate contracts',
                'No physical/budget/Intent implementation or complete business authorization'])
        (BASE/'source-lock-closure.json').write_text(json.dumps(result,indent=2)+'\n')
        failures=sum(len(f['parse_failures']) for f in functions)
        print(result['status'],identity['database'],'functions',len(functions),'parse_failures',failures,
            'dynamic',sum(len(f['dynamic_statements']) for f in functions),flush=True)


class ProbePlugin:
    module=None
    original=None
    def pytest_runtest_setup(self,item):
        if item.originalname==TARGET:
            self.module=item.module;self.original=item.module._assert_occupation_epoch_concurrency
            def wrapped(*args):
                probe(*args)
                return self.original(*args)
            item.module._assert_occupation_epoch_concurrency=wrapped
    def pytest_runtest_teardown(self,item,nextitem):
        if self.module is not None:
            self.module._assert_occupation_epoch_concurrency=self.original
            self.module=None
