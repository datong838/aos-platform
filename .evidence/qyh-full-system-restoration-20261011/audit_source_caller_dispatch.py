"""Read-only AST inventory: preserve original transactions before issuer dispatch."""
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STORES = {
    'AipProductionContractStore': 'aip_production_contract_store.py',
    'AipContentDraftStore': 'aip_content_draft_store.py',
    'AipResponsibilityAssignmentStore': 'aip_responsibility_assignment_store.py',
}
SQL = re.compile(r'\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM|FROM|JOIN)\s+(?:public\.)?([a-z][a-z0-9_]+)', re.I)


def inventory():
    files, constructors, methods = {}, [], []
    for path in sorted((ROOT / 'services/aos-api/aos_api').rglob('*.py')):
        data = path.read_bytes()
        tree = ast.parse(data)
        relevant = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else None
                if name in STORES:
                    relevant = True
                    constructors.append({
                        'file': str(path.relative_to(ROOT)), 'line': node.lineno,
                        'store': name,
                        'factory': ast.unparse(node.args[0]) if node.args else next(
                            (ast.unparse(k.value) for k in node.keywords if k.arg == 'connect_factory'),
                            'DEFAULT'),
                    })
            if isinstance(node, ast.ClassDef) and node.name in STORES:
                relevant = True
                for method in node.body:
                    if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    statements = []
                    calls = []
                    for item in ast.walk(method):
                        if isinstance(item, ast.Constant) and isinstance(item.value, str):
                            statements.extend({'operation': m.group(1).upper(), 'relation': m.group(2).lower()}
                                              for m in SQL.finditer(item.value))
                        if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute):
                            calls.append(ast.unparse(item.func))
                    methods.append({
                        'file': str(path.relative_to(ROOT)), 'store': node.name,
                        'method': method.name, 'line': method.lineno,
                        'parameters': [a.arg for a in [*method.args.posonlyargs, *method.args.args, *method.args.kwonlyargs]],
                        'sqlLiteralReferences': statements,
                        'calls': sorted(set(calls)),
                        'usesCallerConnection': 'conn' in [a.arg for a in [*method.args.args, *method.args.kwonlyargs]],
                    })
        if relevant:
            files[str(path.relative_to(ROOT))] = hashlib.sha256(data).hexdigest()
    assert set(x['store'] for x in methods) == set(STORES)
    return {
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'sourceHashes': files, 'constructors': constructors, 'methods': methods,
        'limitations': ['AST names and SQL literals are routing evidence, not complete dynamic SQL ACL proof',
                       'Injected or caller-owned transactions must not be replaced or split',
                       'Default constructors include readers; constructor replacement alone is unsafe'],
        'databaseOperations': 0, 'productionChanges': False,
    }


if __name__ == '__main__':
    result = inventory()
    destination = Path(__file__).with_name('source-caller-dispatch.json')
    with destination.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'sourceFiles': len(result['sourceHashes']),
                      'constructors': len(result['constructors']),
                      'storeMethods': len(result['methods']),
                      'callerConnectionMethods': sum(m['usesCallerConnection'] for m in result['methods'])}))
