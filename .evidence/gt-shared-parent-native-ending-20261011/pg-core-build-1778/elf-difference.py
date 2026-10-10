"""Bounded ELF section comparison of original and unexecuted rebuilt core."""
import hashlib,json,pathlib,struct,subprocess
B=pathlib.Path(__file__).resolve().parent
old=subprocess.check_output(['docker','exec','aos-source-desktop-shm-20261009','cat','/usr/local/bin/postgres'],timeout=30)
new=(B/'artifacts/postgres').read_bytes()
def sections(raw):
    assert len(raw)<64*1024*1024 and raw[:6]==b'\x7fELF\x02\x01'
    e=struct.unpack_from('<16sHHIQQQIHHHHHH',raw);off,size,count,ni=e[6],e[11],e[12],e[13]
    assert size==64 and 0<count<8192 and ni<count and off+size*count<=len(raw)
    sh=[struct.unpack_from('<IIQQQQIIQQ',raw,off+j*size) for j in range(count)]
    names=raw[sh[ni][4]:sh[ni][4]+sh[ni][5]];out={}
    for x in sh:
        assert x[0]<len(names);end=names.find(b'\0',x[0]);assert end>=0
        name=names[x[0]:end].decode('ascii');assert len(name)<256
        content=b'' if x[1]==8 else raw[x[4]:x[4]+x[5]]
        if x[1]!=8:assert x[4]+x[5]<=len(raw)
        out[name]={'size':x[5],'sha256':hashlib.sha256(content).hexdigest(),'file_bytes':content}
    return out
a=sections(old);b=sections(new);diff={}
for name in sorted(set(a)|set(b)):
    x=a.get(name);y=b.get(name)
    if x and y and x['size']==y['size'] and x['sha256']==y['sha256']:continue
    diff[name]={'original':{k:v for k,v in x.items() if k!='file_bytes'} if x else None,'rebuilt':{k:v for k,v in y.items() if k!='file_bytes'} if y else None}
    if x and y:
        diff[name]['first_mismatch']=next((i for i,(p,q) in enumerate(zip(x['file_bytes'],y['file_bytes'])) if p!=q),None)
        diff[name]['differing_overlap_bytes']=sum(p!=q for p,q in zip(x['file_bytes'],y['file_bytes']))
out={'original_sha256':hashlib.sha256(old).hexdigest(),'rebuilt_sha256':hashlib.sha256(new).hexdigest(),'original_size':len(old),'rebuilt_size':len(new),'equal_section_names':[n for n in a if n in b and a[n]['size']==b[n]['size'] and a[n]['sha256']==b[n]['sha256']],'different_sections':diff,'original_binary_reproduced':False,'no_execution_or_binary_patch':True}
(B/'elf-difference.json').open('x').write(json.dumps(out,indent=2)+'\n')
print(json.dumps({'sizes':[len(old),len(new)],'different_sections':{n:{k:v for k,v in d.items() if k in ['first_mismatch','differing_overlap_bytes']} for n,d in diff.items()}}))
