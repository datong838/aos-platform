from pathlib import Path
import json,hashlib
B=Path(__file__).resolve().parent
def parse(path):
 result={}
 for block in path.read_text().strip().split('\n\n'):
  fields=dict(line.split(':',1) for line in block.splitlines() if ':' in line)
  assert fields['P'] not in result
  result[fields['P']]={k:fields[k] for k in ('P','V','A','C')}
 return result
a=parse(B.parent/'build-dependency-lock-1809/installed.txt');b=parse(B/'rebuilt-installed.txt')
differences=[k for k in sorted(a.keys()|b.keys()) if a.get(k)!=b.get(k)]
x=(B/'original-world').read_bytes();y=(B/'rebuilt-world').read_bytes()
result={'reference_packages':len(a),'rebuilt_packages':len(b),'differences':differences,'world_equal':x==y,'world_sha256':hashlib.sha256(y).hexdigest(),'full_source_build_trust':False,'execution_authorized':False}
assert len(a)==len(b)==156 and not differences and x==y
(B/'package-result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
