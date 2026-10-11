"""Bounded read-only reconciliation of the user's existing Docker disk files."""
import hashlib
import json
import socket
import subprocess
from pathlib import Path

R = Path(__file__).resolve().parent
ROOT = R.parents[1]
target = R / 'storage-recovery-locations.json'
assert not target.exists(), 'Reconcile existing observation; never overwrite'
files = []
for p in (Path('/Volumes/NVME2T/Docker/Docker.raw'),
          Path('/Volumes/NVME2T/Docker/data/Docker.raw.aos-recovery-20260910')):
    if p.exists():
        s = p.stat()
        files.append({'path': str(p), 'size': s.st_size, 'allocatedBytes': s.st_blocks * 512,
                      'mtimeNs': s.st_mtime_ns, 'inode': s.st_ino,
                      'contentRead': False, 'contentIntegrityVerified': False})
status = subprocess.run(['docker', 'desktop', 'status'], capture_output=True, text=True, timeout=8)
assert status.returncode == 0, 'Supported Desktop status unavailable'
rows = dict(line.split(None, 1) for line in status.stdout.splitlines()[1:] if line.strip())
sock = socket.socket(socket.AF_UNIX)
sock.settimeout(4)
ping = {}
try:
    sock.connect('/Users/ddt/.docker/run/docker.sock')
    ping['socketConnected'] = True
    sock.sendall(b'GET /_ping HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
    ping['responded'] = bool(sock.recv(1024))
except (TimeoutError, OSError) as error:
    ping['errorType'] = type(error).__name__
finally:
    sock.close()
record = ROOT / '.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5cb4-bg00o-isolated-eval-object-store-verification-20260929.md'
reader = ROOT / 'services/aos-api/aos_api/aip_eval_object_reader.py'
original = record.read_text()
assert '无 S3 PUT/GET' in original and '新建且仅本波使用' in original
result = {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
          'authority': 'AOS-001891', 'task': 'qyh-source-boundary-rehearsal-20261011',
          'diskFileMetadata': files, 'desktopStatus': rows, 'desktopPing': ping,
          'settingsReadDeniedByMacOS': True,
          'historicalMinioRoundtripAccepted': False,
          'existingEvalReaderReusableOnlyWithinOriginalNamespace': True,
          'historicalEvidenceHash': hashlib.sha256(record.read_bytes()).hexdigest(),
          'existingEvalReaderHash': hashlib.sha256(reader.read_bytes()).hexdigest(),
          'scriptHash': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'rawDiskMounted': False, 'engineRestarted': False, 'resourcesCreatedOrDeleted': False,
          'databaseWrites': 0, 'objectReads': 0, 'objectWrites': 0,
          'historicalMediaLocationFullyVerified': False, 'fullRestorationAccepted': False}
with target.open('x') as stream:
    json.dump(result, stream, indent=2, ensure_ascii=False)
    stream.write('\n')
print(json.dumps({'existingDiskFiles': len(files), 'desktopStatus': rows,
                  'desktopPing': ping, 'diskContentIntegrityVerified': False}, ensure_ascii=False))
