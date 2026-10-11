import json,sys
from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row
sys.path.insert(0,"/code/services/aos-api")
from aos_api.asset_registry.workshop_catalog_source import PostgresWorkshopCatalogSource
@contextmanager
def connection():
 with psycopg.connect("postgresql://aos_app@/aos_meta_head?host=/pgsocket",row_factory=dict_row) as c:
  c.execute("SET TRANSACTION READ ONLY")
  identity=c.execute("SELECT system_identifier::text FROM pg_control_system()").fetchone()
  assert identity["system_identifier"]=="7695294217975042088"
  yield c
with connection() as c:
 rows=c.execute("SELECT l.lock_payload->'permissionDiff' AS permissions FROM bundle_installation i JOIN bundle_installation_revision r ON r.installation_pk=i.installation_pk AND r.revision=i.active_revision JOIN bundle_composition_lock l ON l.composition_pk=r.composition_pk AND l.revision=r.lock_revision WHERE i.org_id='org-org' AND i.project_id='dev-project'").fetchall()
 # Markings are inspected below; no grant is inferred.
 print(json.dumps({"lockPermissionShapes":[list((x['permissions'] or {}).keys()) for x in rows]}))
source=PostgresWorkshopCatalogSource(connection)
for runtime in (False,True):
 try:
  items=source._read_candidate_bundles(org_id='org-org',project_id='dev-project',markings=[],runtime_only=runtime)
  print(json.dumps({"runtimeOnly":runtime,"status":"PARSED","candidates":[{"installation":x.installation_id,"activeRevision":x.active_revision,"bundle":x.bundle.bundle_id,"version":x.bundle.version,"workshopPaths":[a['relativePath'] for a in x.bundle.artifacts if str(a['relativePath']).startswith('content/workshops/')]} for x in items]}))
 except Exception as e:
  print(json.dumps({"runtimeOnly":runtime,"status":"REJECTED","errorType":type(e).__name__,"causeType":type(e.__cause__).__name__ if e.__cause__ else None,"reason":str(e)}))
