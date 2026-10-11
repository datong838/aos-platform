import inspect,json,hashlib,pathlib
from aos_api import aip_shared_parent_atomic_admission as a
b=pathlib.Path(__file__).resolve().parent
out={n:hashlib.sha256('\n'.join(f()).encode()).hexdigest() for n,f in inspect.getmembers(a,inspect.isfunction) if n.startswith('shared_parent_') and n.endswith('_statements')}
(b/'beforeimage.json').open('x').write(json.dumps(out,indent=2)+'\n');print(len(out))
