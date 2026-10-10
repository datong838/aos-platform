"""Read ELF dynamic symbols; no container mutation or binary installation."""
import hashlib,json,struct,subprocess
from pathlib import Path
B=Path('.evidence/gt-shared-parent-atomic-admission-finalizer-20261010');lab=json.loads(Path('.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
identity=json.loads(subprocess.check_output(['docker','inspect',lab['name']]))[0]
assert identity['Id']==lab['container_id'] and identity['Image']==lab['image'] and identity['State']['Running']
data=subprocess.check_output(['docker','exec',lab['name'],'cat','/usr/local/bin/postgres'])
assert data[:6]==b'\x7fELF\x02\x01'
h=struct.unpack_from('<16sHHIQQQIHHHHHH',data);sections=[struct.unpack_from('<IIQQQQIIQQ',data,h[6]+i*h[11]) for i in range(h[12])]
found=[]
for s in sections:
 if s[1]!=11:continue
 strings=sections[s[6]];names=data[strings[4]:strings[4]+strings[5]]
 for offset in range(s[4],s[4]+s[5],s[9]):
  n,info,other,index,value,size=struct.unpack_from('<IBBHQQ',data,offset)
  name=names[n:names.find(b'\0',n)].decode()
  if name=='AfterTriggerPendingOnRel':found.append(dict(name=name,binding=info>>4,type=info&15,visibility=other&3,section=index,value=value,size=size))
assert len(found)==1 and found[0]['binding']==1 and found[0]['type']==2 and found[0]['section']!=0 and found[0]['visibility']==0
result=dict(status='EXACT_ISOLATED_ELF_DYNAMIC_SYMBOL_VERIFIED',authority='AOS-001744',container=lab['container_id'],image=lab['image'],binary='/usr/local/bin/postgres',binary_sha256=hashlib.sha256(data).hexdigest(),symbol=found[0],no_container_mutation=True,no_native_helper_installed=True,no_execution_authority=True)
(B/'native-symbol-verification-1744.json').open('x').write(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(status=result['status'],symbol=found[0]['name'],binary_sha256=result['binary_sha256'])))
