"""Exact authorized installation/operation metadata audit; no commands replayed."""
from pathlib import Path
import importlib.util,json,subprocess
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('c',P/'current_protected_identities.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
QUERY="""SELECT json_build_object(
 'installation',(SELECT row_to_json(x) FROM (SELECT i.installation_id::text,i.current_revision,i.active_revision,i.previous_active_revision,i.etag_version,r.state,r.requested_by,r.decision_id::text,i.created_by FROM bundle_installation i JOIN bundle_installation_revision r ON r.org_id=i.org_id AND r.project_id=i.project_id AND r.installation_pk=i.installation_pk AND r.revision=i.current_revision WHERE i.org_id='org-org' AND i.project_id='dev-project' AND i.installation_id='ab2fd72f-d81c-400d-bbbc-e1589a159d6b')x),
 'operations',(SELECT coalesce(json_agg(row_to_json(x) ORDER BY created_at),'[]') FROM (SELECT operation_id::text,kind,status,phase,revision,requested_by,approved_by,expected_installation_etag,deadline,failure_code,idempotency_key,created_at FROM extension_runtime_operation WHERE org_id='org-org' AND project_id='dev-project' AND installation_id='ab2fd72f-d81c-400d-bbbc-e1589a159d6b')x),
 'decisions',(SELECT coalesce(json_agg(row_to_json(x) ORDER BY created_at),'[]') FROM (SELECT decision_id::text,submitted_revision,decision,actor,lock_hash,created_at FROM bundle_installation_decision WHERE org_id='org-org' AND project_id='dev-project' AND installation_pk=(SELECT installation_pk FROM bundle_installation WHERE org_id='org-org' AND project_id='dev-project' AND installation_id='ab2fd72f-d81c-400d-bbbc-e1589a159d6b'))x),
 'commands',(SELECT coalesce(json_agg(row_to_json(x) ORDER BY created_at),'[]') FROM (SELECT operation,idempotency_key,subject,status_code,response_etag,created_at FROM bundle_installation_command WHERE org_id='org-org' AND project_id='dev-project' AND response_json::text LIKE '%ab2fd72f-d81c-400d-bbbc-e1589a159d6b%')x),
 'currentHumanMembership',(SELECT coalesce(json_agg(row_to_json(x)),'[]') FROM (SELECT role FROM meta_membership WHERE org_id='org-org' AND project_id='dev-project' AND subject='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657')x));"""
if __name__=='__main__':
 try:x=json.loads(c.read(QUERY))
 except subprocess.CalledProcessError as e:
  print(e.stderr);raise
 path=P/'current-installation-operation-readonly-reconciliation-20261013.json'
 with path.open('x') as f:json.dump({'native':x,'unknownOperationsReplayed':False,'installationChanged':False,'currentDatabaseWrites':False},f,ensure_ascii=False,indent=2)
 print(json.dumps(x,ensure_ascii=False,indent=2))
