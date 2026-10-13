"""Read-only audit of original directory function privilege and denied raw tables."""
from pathlib import Path
import importlib.util,json,sys
P=Path(__file__).resolve().parent;ROOT=P.parents[1]
s=importlib.util.spec_from_file_location('c',P/'current_protected_identities.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
values=c._runtime_file_dsns(c.CREDENTIAL);proof={}
with c.psycopg.connect(values['directory'],row_factory=c.dict_row,connect_timeout=5) as conn:
 conn.read_only=True
 proof['nativePrivilege']=dict(conn.execute("SELECT session_user,current_user,pg_has_role(session_user,'aos_extension_directory','member') directory_member,has_function_privilege(session_user,'extension_runtime_read_host_assignments()','EXECUTE') can_read_assignments,has_table_privilege(session_user,'extension_runtime_host_assignment','SELECT') can_raw_read_assignment").fetchone());conn.commit()
 try:
  with conn.transaction():rows=conn.execute('SELECT org_id,project_id,assignment_revision FROM extension_runtime_read_host_assignments()').fetchall()
  proof['originalDirectoryRows']=[dict(x) for x in rows]
 except c.psycopg.Error as e:proof['nativeDirectoryError']={'SQLSTATE':e.sqlstate,'functionExecuteDenied':e.sqlstate=='42501'}
proof['nativeTableAcl']=json.loads(c.read("SELECT json_agg(row_to_json(x)) FROM (SELECT relname,relacl::text,relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid IN ('extension_runtime_host_assignment'::regclass,'extension_runtime_host_identity'::regclass))x;"))
proof['currentDatabaseWrites']=False;proof['roleMembershipChanged']=False;proof['originalMigrationContract']='ar1_003 explicitly revokes raw table reads and exposes bound readonly SECURITY DEFINER directory function'
(P/'host-reader-permission-audit-20261013.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof))
