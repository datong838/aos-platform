import importlib.util,json,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('precommit_mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001650'
(B/'leases-before.json').write_text(json.dumps(m.load_leases(m.DEFAULT_PATHS),indent=2))
t=m.start_task(m.DEFAULT_PATHS,task_id=B.name,owner='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2',expected_revision=a['project_revision'],scope=['aos-platform/.evidence/'+B.name,'isolatedDocker:desktop-linux/aos-precommit-probe-20261009'],excluded_scope=['aos-platform/services','aos-platform/apps','authoritativeDB'],expected_outputs=['Native two-order PRE_COMMIT candidate counterexample on new owned lab; retained xid readback and all old resources unchanged; no Source or business authorization'],lease_expires_at=(datetime.now(timezone.utc)+timedelta(hours=4)).isoformat())
(B/'task.json').write_text(json.dumps(t,indent=2));print(t['task_id'],t['base_revision'])
