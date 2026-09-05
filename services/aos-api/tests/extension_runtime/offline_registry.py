"""Exact temporary localhost registry for isolated OCI tests only."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import time
import urllib.request
import uuid


def cleanup(docker,name,ref,helper):
    targets=(('container',name),('image',ref),('image',helper))
    for kind,target in targets:
        try:
            subprocess.run([*docker,kind,'rm',*(['-f'] if kind=='container' else []),target],
                capture_output=True,timeout=15)
        except (OSError,subprocess.TimeoutExpired):
            pass  # An uncertain removal is resolved by independent readback below.
    unresolved=[]
    for kind,target in targets:
        try:
            result=subprocess.run([*docker,kind,'inspect',target],capture_output=True,text=True,timeout=15)
            if result.returncode!=0 and 'No such' in result.stderr:
                continue
        except (OSError,subprocess.TimeoutExpired):
            pass
        unresolved.append(target)
    if unresolved:
        raise RuntimeError('test registry cleanup not confirmed: '+', '.join(unresolved))


@contextmanager
def cached_registry_image(directory, image_id, context):
    directory.mkdir()
    docker=['docker','--context',context]
    archive=directory/'image.tar'
    subprocess.run([*docker,'image','save','-o',str(archive),image_id],check=True,timeout=60,capture_output=True)
    data=directory/'fixture';(data/'blobs').mkdir(parents=True)
    with tarfile.open(archive) as source:
        index=json.load(source.extractfile('manifest.json'))
        assert len(index)==1
        def blob(name,kind):
            member=source.getmember(name)
            assert 0<=member.size<=256*1024*1024
            raw=source.extractfile(member).read()
            digest=hashlib.sha256(raw).hexdigest()
            (data/'blobs'/digest).write_bytes(raw)
            return {'mediaType':kind,'digest':'sha256:'+digest,'size':len(raw)}
        config=blob(index[0]['Config'],'application/vnd.oci.image.config.v1+json')
        layers=[blob(name,'application/vnd.oci.image.layer.v1.tar') for name in index[0]['Layers']]
    raw=json.dumps({'schemaVersion':2,'mediaType':'application/vnd.oci.image.manifest.v1+json',
        'config':config,'layers':layers},separators=(',',':')).encode()
    (data/'manifest.json').write_bytes(raw)
    digest='sha256:'+hashlib.sha256(raw).hexdigest()
    shutil.copyfile(Path(__file__).with_name('static_registry_server.py'),directory/'server.py')
    (directory/'Dockerfile').write_text('FROM python:3.11-alpine\nCOPY fixture /fixture\nCOPY server.py /server.py\nUSER 65534:65534\nCMD ["python","/server.py"]\n')
    helper=subprocess.check_output([*docker,'build','--network=none','--pull=false','-q',str(directory)],text=True,timeout=60).strip()
    name='ar1-registry-'+uuid.uuid4().hex
    ref='127.0.0.1:18433/aos-test@'+digest
    try:
        subprocess.run([*docker,'run','-d','--name',name,'--read-only','--cap-drop=ALL',
            '--security-opt=no-new-privileges','--memory=256m','--pids-limit=32',
            '-p','127.0.0.1:18433:5000',helper],check=True,capture_output=True,timeout=15)
        end=time.monotonic()+10
        while True:
            try:
                with urllib.request.urlopen('http://127.0.0.1:18433/v2/',timeout=1) as response:
                    assert response.status==200
                break
            except OSError:
                if time.monotonic()>end:raise
                time.sleep(.1)
        subprocess.run([*docker,'pull',ref],check=True,capture_output=True,timeout=60)
        yield digest,config['digest']
    finally:
        cleanup(docker,name,ref,helper)
