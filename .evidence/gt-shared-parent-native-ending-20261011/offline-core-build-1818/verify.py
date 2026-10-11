from pathlib import Path
import hashlib,json
B=Path(__file__).resolve().parent
reference=json.loads((B.parent/'pg-core-build-1778/r3/verification.json').read_text())['files']
checks={}
for name,expected in reference.items():
 actual=hashlib.sha256((B/'output/artifacts'/name).read_bytes()).hexdigest()
 checks[name]={'sha256':actual,'reference_sha256':expected['rebuilt_sha256'],'controlled_build_equal':actual==expected['rebuilt_sha256'],'historical_installed_equal':actual==expected['installed_sha256']}
result={'checks':checks,'controlled_build_equal':all(x['controlled_build_equal'] for x in checks.values()),'full_source_build_trust':False,'execution_authorized':False,'full_task_delivered':False}
(B/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result));assert result['controlled_build_equal']
