"""Trace original issuance callers before narrowing current Source ACLs."""
import ast
import argparse
import re
import hashlib
import json
from pathlib import Path
import release_transition as T

ROOT = T.ROOT
FILES = [
    'services/aos-api/aos_api/aip_production_contract_store.py',
    'services/aos-api/aos_api/aip_content_draft_store.py',
    'services/aos-api/aos_api/aip_bi_plan_issuer_connection.py',
    'services/aos-api/aos_api/routers/aip_production_contracts.py',
    'services/aos-api/tests/extension_runtime/test_plan_receipt_writer_protocol_pg.py',
    'services/aos-api/aos_api/ecommerce_runtime_workshop_catalog.py',
    'services/aos-api/aos_api/aip_responsibility_assignment_store.py',
]


def static_trace():
    paths = {path: ROOT/path for path in FILES}
    tree = ast.parse(paths[FILES[0]].read_text())
    fixed, dynamic = [], []
    for node in ast.walk(tree):
        if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            continue
        for call in ast.walk(node):
            if (isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute)
                    and call.func.attr == '_receipt'):
                assert len(call.args) >= 3, 'Unknown issuance call shape'
                operation = call.args[2]
                row = {'method':node.name,'line':call.lineno}
                if isinstance(operation,ast.Constant) and isinstance(operation.value,str):
                    fixed.append({**row,'operation':operation.value})
                else:
                    dynamic.append({**row,'expression':ast.unparse(operation)})
    protocol = ast.parse(paths[FILES[4]].read_text())
    catalog = {}
    for node in protocol.body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
            if node.targets[0].id in ('PLAN_OPERATIONS','CONTRACT_OPERATIONS'):
                catalog[node.targets[0].id] = list(ast.literal_eval(node.value))
    assert set(catalog) == {'PLAN_OPERATIONS','CONTRACT_OPERATIONS'}
    direct = []
    pattern = re.compile(r'(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+(?:public\.)?(aip_responsibility_plan_head|aip_responsibility_plan_revision|aip_production_contract_receipt)\b',re.I)
    for path in ROOT.joinpath('services/aos-api/aos_api').rglob('*.py'):
        source = path.read_text()
        hits = [{'line': source[:match.start()].count('\n')+1, 'operation':match.group(1).upper(), 'table':match.group(2)} for match in pattern.finditer(source)]
        if hits:
            direct.append({'file':str(path.relative_to(ROOT)), 'sha256':hashlib.sha256(source.encode()).hexdigest(), 'writeSites':hits})
    return {'directSourceWriterFiles':sorted(direct,key=lambda row:row['file']),
        'successorWriterRequiresSamePlanIssuerWithoutSharedReceipt':True,
        'sourceHashes':{p:hashlib.sha256(f.read_bytes()).hexdigest() for p,f in paths.items()},
        'fixedProductionReceiptCallSites':fixed,'dynamicPlanReceiptCallSites':dynamic,
        'protocolOperationCatalog':catalog,
        'fixedOperationsMissingFromProtocol':sorted({x['operation'] for x in fixed}-set(catalog['CONTRACT_OPERATIONS'])),
        'protocolIsProductionMigration':False,
        'threeDynamicPlanCallsRequireOriginalPerMethodAllowlist':True,
        'contentDraftHasSeparateDirectReceiptInsert':True,
        'existingIssuerConnectorMustNotBeReplacedByRuntimeMember':True}


def current_readback():
    with T.factory() as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        conn.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
        rows = conn.execute('''SELECT operation,count(*) AS count
            FROM aip_production_contract_receipt WHERE org_id='org-org' AND project_id='dev-project'
            GROUP BY operation ORDER BY operation''').fetchall()
        acl = conn.execute('''SELECT name,
            has_table_privilege('aos_runtime',name,'SELECT') AS read,
            has_table_privilege('aos_runtime',name,'INSERT') AS insert,
            has_table_privilege('aos_runtime',name,'UPDATE') AS update,
            has_table_privilege('aos_runtime',name,'DELETE') AS delete
            FROM unnest(ARRAY['public.aip_responsibility_plan_head',
            'public.aip_responsibility_plan_revision','public.aip_production_contract_receipt']) AS name
            ORDER BY name''').fetchall()
        issuer = conn.execute("SELECT rolname,rolcanlogin,rolsuper,rolbypassrls,rolinherit FROM pg_roles WHERE rolname='aos_bi_plan_issuer'").fetchall()
        return {'scope':{'orgId':'org-org','projectId':'dev-project'},
            'receiptOperationCounts':[dict(row) for row in rows],
            'sourceRuntimeAcl':[dict(row) for row in acl],
            'existingBiIssuerRole':[dict(row) for row in issuer]}


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--revision',choices=('1','2'),default='1')
    args=parser.parse_args()
    output = T.R/('source-writer-impact.json' if args.revision=='1' else 'source-writer-impact-r2.json')
    assert not output.exists(), 'Existing audit must not be overwritten'
    T.H.preflight(T.R/'private/restored-identity.json')
    trace = static_trace()
    first, second = current_readback(), current_readback()
    assert first == second, 'Current source state changed between independent reads'
    result = {**trace,**first,'independentReadbackExact':True,
        'databaseWrites':0,'sourceAclChanged':False,
        'runtimeSourceWriteRemovalSafeNow':False,
        'nextImplementationRequirements':[
            'Separate Plan (generic/BI/successor), Content and Contract issuer connections with complete existing caller transactions',
            'Map all original receipt operation allowlists and full dependency SELECT/write grants',
            'Preserve original BI Plan issuer identity, serializable scopes, Receipt/CAS/commit and rollback',
            'Full restored-clone original Store positive/canary/forgery regression before current ACL tightening'],
        'catalogVisibilityRequiresReadyEnabledUnfencedUiResource':True,
        'formalPublisherOrEightWorkbenchesAccepted':False}
    with output.open('x') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2)
        stream.write('\n')
    print(json.dumps({'fixedCalls':len(trace['fixedProductionReceiptCallSites']),
        'dynamicCalls':len(trace['dynamicPlanReceiptCallSites']),
        'fixedOperationsMissing':trace['fixedOperationsMissingFromProtocol'],
        'historicalReceiptOperations':len(first['receiptOperationCounts']),
        'sourceWriteRevocationSafe':False}))
