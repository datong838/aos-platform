"""Read-only code audit; this does not execute or grant business capacity."""
import ast
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[2]
api = root / 'services/aos-api/aos_api'
watched = ['aip_provider_capacity_source_consumer.py',
           'aip_provider_capacity_source_issuer.py',
           'aip_provider_capacity_publication_transaction.py',
           'aip_model_capacity_authority.py',
           'aip_model_capacity_reservation.py',
           'aip_binding_formal_evaluator.py',
           'aip_binding_formal_evaluator_contracts.py']
reader = 'read_current_capacity_source'
calls = []
imports = []
for path in sorted(api.rglob('*.py')):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    aliases = {reader}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == reader:
                    aliases.add(alias.asname or reader)
                    imports.append({'file': str(path.relative_to(root)), 'line': node.lineno})
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if ((isinstance(function, ast.Name) and function.id in aliases)
            or (isinstance(function, ast.Attribute) and function.attr == reader)):
            calls.append({'file': str(path.relative_to(root)), 'line': node.lineno})

consumer_tree = ast.parse((api / watched[0]).read_text())
entry = next(n for n in consumer_tree.body if isinstance(n, ast.FunctionDef) and n.name == reader)
entry_calls = [ast.unparse(n.func) for n in ast.walk(entry) if isinstance(n, ast.Call)]
assert 'capacity_source_preparation_bytes' in entry_calls
assert 'require_capacity_issuer_identity' in entry_calls
assert not calls and not imports, (calls, imports)

pool_tree = ast.parse((api / 'aip_model_capacity_authority.py').read_text())
pool = next(n for n in pool_tree.body if isinstance(n, ast.ClassDef) and n.name == 'CapacityPoolRevisionCreate')
pool_fields = [n.target.id for n in pool.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)]
assert 'provider_ref' in pool_fields and 'max_concurrency' in pool_fields
assert not any('source' in field for field in pool_fields)
formal = (api / 'aip_binding_formal_evaluator_contracts.py').read_text()
assert "allowed = {'EvidenceBundleRevision'} if name == 'source_refs'" in formal
assert 'ProviderCapacitySourceRevision' not in formal
result = {
    'schema': 'aos-capacity-business-consumer-call-audit/v1',
    'observed_at': datetime.now(timezone.utc).isoformat(),
    'head': subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip(),
    'authority_revision': 'AOS-001460',
    'runtime_scan': 'all aos_api Python AST direct name/attribute calls and from-imports; dynamic loading not proven absent',
    'runtime_direct_calls': calls,
    'runtime_from_imports': imports,
    'current_reader_authentication': 'original issuance command freshly authenticated; original maker binding; controlled SCRAM issuer connection',
    'pool_fields': pool_fields,
    'formal_source_refs_kind': 'EvidenceBundleRevision (License evidence), not ProviderCapacitySourceRevision',
    'files': {str((api / name).relative_to(root)): hashlib.sha256((api / name).read_bytes()).hexdigest() for name in watched},
    'conclusion': 'Current issuer reader is not yet business capacity integration; independent consumer identity and exact Source-to-pool/occupation authorization remain required',
    'full_source_delivery': False,
    'business_first_chain': False,
}
out = Path(__file__).with_name('business-consumer-callers-audit.json')
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'direct_runtime_calls': len(calls), 'source_bound_pool': False,
                  'formal_capacity_source_integration': False, 'files_hashed': len(watched)}))
