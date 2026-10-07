"""One claimed latest-source API refresh; no database writes or migrations."""
import hashlib
import importlib.util
import io
import json
import os
import signal
import subprocess
import sys
import tarfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

E = Path(__file__).resolve().parent
R = E.parents[1]
HEAD = "11b9dead"
TASK = "current157-api-refresh-20261008"
old = json.loads((R / ".evidence/current157-maintenance-20261008/current-window-result.json").read_text())
old_service = next(x for x in old["services"] if x["port"] == 8080)
original = next(x for x in json.loads((Path(old["state"]) / "original-services.json").read_text()) if x["port"] == 8080)
def load(name, file):
    spec = importlib.util.spec_from_file_location(name, R / file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
mem = load("refresh_mem", "scripts/memory/memoryctl.py")
maint = load("refresh_process", "scripts/a0v_current_142_maintenance.py")
bootstrap = load("refresh_connect", "scripts/a0v_current_preview_bootstrap.py")
g = load("refresh_snapshot", "scripts/a0v_current_142_restore_gate.py")
def guard():
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=R, text=True).strip().startswith(HEAD)
    assert mem.load_authority()["project_revision"] == "AOS-001493"
    matches = [x for x in mem.load_leases(mem.DEFAULT_PATHS)["leases"] if x["task_id"] == TASK]
    assert len(matches) == 1 and matches[0]["owner"] == "codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2"
    assert matches[0]["status"] == "ACTIVE" and datetime.fromisoformat(matches[0]["lease_expires_at"]) > datetime.now(timezone.utc)
    assert matches[0] == json.loads((mem.DEFAULT_PATHS.receipts_path / "tasks" / (TASK + ".json")).read_text())
    pg = json.loads(subprocess.check_output(["docker", "--context", "colima-aos-extension", "inspect", "aos-a0v-recovery-pg"]))[0]
    maint.require_source(pg)
    assert pg["Id"] == old["source_id"] and pg["State"]["StartedAt"] == old["pg_started"]
guard()
with os.fdopen(os.open(E / "claim.json", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as out:
    json.dump({"task": TASK, "head": HEAD}, out); out.flush(); os.fsync(out.fileno())
stage = "prepare"
def save(name, value):
    with os.fdopen(os.open(E / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as out:
        json.dump(value, out, indent=2, default=str); out.flush(); os.fsync(out.fileno())
def verify_data():
    import psycopg
    with psycopg.connect(**bootstrap._connection_parameters()) as conn:
        conn.read_only = True
        conn.execute("SET LOCAL timezone='UTC';SET LOCAL search_path=pg_catalog,public")
        def query(sql): return conn.execute(sql).fetchone()[0]
        snapshot = g.snapshot(query)
        assert snapshot == json.loads((Path(old["state"]) / "public-after-startup.json").read_text())
        assert snapshot["version"] == "a0v_157"
        before = json.loads((Path(old["state"]) / "old-data-after-startup.json").read_text())
        actual = {}; names = list(before)
        for index in range(0, len(names), 40):
            parts = [f"SELECT {g.literal(name)} AS name,count(*) AS count,encode(sha256(convert_to(coalesce(string_agg(h,'' ORDER BY h),''),'UTF8')),'hex') AS sha256 FROM (SELECT encode(sha256(convert_to(row_to_json(t)::text,'UTF8')),'hex') AS h FROM {g.public(name)} t) hashes" for name in names[index:index+40]]
            for row in query("SELECT json_agg(x ORDER BY name) AS value FROM (" + " UNION ALL ".join(parts) + ") x"):
                actual[row["name"]] = {"count": row["count"], "sha256": row["sha256"]}
        assert before == actual
        conn.rollback()
    return {"version": "a0v_157", "public_catalog_unchanged": True, "old_tables_unchanged": len(before)}
try:
    save("before-data.json", verify_data())
    parent = Path(old["state"]).parent
    root = parent / ("committed-code-" + HEAD)
    root.mkdir(mode=0o700)
    archive = subprocess.check_output(["git", "archive", HEAD, "services/aos-api", "scripts", "bundles"], cwd=R)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar.getmembers():
            assert Path(member.name).parts[0] in {"services", "scripts", "bundles"}
            assert ".." not in Path(member.name).parts and (member.isfile() or member.isdir())
        tar.extractall(root)
    argv = list(old_service["argv"]); argv[1] = str(root / "scripts/a0v_current_preview_http.py")
    environment = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR", "LANG") if key in os.environ}
    environment.update(original["environment"])
    preflight = subprocess.run(argv[:-1], cwd=original["cwd"], env=environment, capture_output=True, timeout=90)
    save("preflight.json", {"exit": preflight.returncode, "stdout": preflight.stdout.decode(), "stderr": preflight.stderr.decode()})
    assert preflight.returncode == 0
    report = json.loads(preflight.stdout.strip().splitlines()[-1])
    assert report["outcome"] == "CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN" and report["version"] == "a0v_157" and report["runtimeBindings"] == 0
    guard()
    fp = maint.read_service_candidate(pid=old_service["pid"], expected_argv=old_service["argv"], expected_cwd=original["cwd"], expected_port=8080, expected_child_argv=original["helper_argv"])
    assert fp["started"] == old_service["fingerprint"]["started"]
    stage = "stop_exact_api"
    save("stop-intent.json", {"fingerprint": fp, "archive_sha256": hashlib.sha256(archive).hexdigest(), "root": str(root)})
    os.kill(old_service["pid"], signal.SIGTERM)
    for _ in range(100):
        if not subprocess.run(["lsof", "-nP", "-iTCP:8080", "-sTCP:LISTEN", "-t"], capture_output=True).stdout.strip(): break
        time.sleep(.1)
    else: raise RuntimeError("Original API listener did not stop")
    guard(); stage = "start_latest_api"
    save("start-intent.json", {"argv": argv, "cwd": original["cwd"], "head": HEAD})
    with os.fdopen(os.open(E / "api.log", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb") as out:
        process = subprocess.Popen(argv, cwd=original["cwd"], env=environment, stdout=out, stderr=out, start_new_session=True)
    save("started.json", {"pid": process.pid})
    for _ in range(100):
        assert process.poll() is None
        try:
            with urllib.request.urlopen("http://127.0.0.1:8080/v1/ready", timeout=2) as response:
                if response.status == 200: break
        except OSError: pass
        time.sleep(.2)
    else: raise RuntimeError("Latest API readiness failed")
    stage = "verify_latest_api"
    fp = maint.read_service_candidate(pid=process.pid, expected_argv=argv, expected_cwd=original["cwd"], expected_port=8080, expected_child_argv=original["helper_argv"])
    guard(); after = verify_data()
    save("result.json", {"status": "LATEST11B9_API157_SIGNED_READONLY_GREEN_BROWSER_PENDING", "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=R, text=True).strip(), "fingerprint": fp, "argv": argv, "source_id": old["source_id"], "volume": old["volume"], "pg_started_unchanged": old["pg_started"], "after": after, "signed_preflight": report, "host_workers_provider_off": True, "migration_attempted": False})
    print("LATEST11B9_API157_SIGNED_READONLY_GREEN_BROWSER_PENDING", flush=True)
except Exception as error:
    save("failure.json", {"stage": stage, "type": type(error).__name__, "unknown_reconcile_only": True})
    raise
