"""Restored preparation uses bound directory projection, never Host table grants."""
import importlib.util
from contextlib import contextmanager
from pathlib import Path
import pytest
from psycopg.pq import TransactionStatus
SCRIPT=Path(__file__).resolve().parents[4]/'scripts/a0v_current_runtime_host_preflight.py'
@pytest.fixture
def gate():
 s=importlib.util.spec_from_file_location('qyh_directory_preparation',SCRIPT);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class Info:transaction_status=TransactionStatus.IDLE
class Directory:
 info=Info()
 def __init__(self,rows):self.rows=rows;self.queries=[]
 @contextmanager
 def transaction(self):yield
 def execute(self,query):
  self.queries.append(query)
  assert 'FROM extension_runtime_read_host_assignments()' in query
  assert 'host_identity ' not in query and 'host_assignment ' not in query
  return self
 def fetchall(self):return self.rows

def report(enabled=0,cluster='same'):
 return {'identity':{'database':'aos_meta_head','cluster':cluster,'schema':'a0v_161','orgId':'org-org','projectId':'dev-project','tables':650},'inventory':{'enabledBindings':enabled}}

def test_restored_projection_uses_original_directory_and_preserves_unverified_configuration(gate):
 directory=Directory([{'org_id':'org-org','project_id':'dev-project','assignment_revision':1}]);calls=[]
 def reread():calls.append(True);return report()
 result=gate.require_restored_preparation_directory(directory,initial_report=report(),read_report=reread)
 assert calls==[True] and len(directory.queries)==1
 assert result['admissionMode']=='PREPARATION_ONLY'
 assert result['assignmentRevision']==1 and result['directoryAssignmentScope']==['org-org','dev-project']
 assert result['configurationCandidatesVerified'] is False and result['candidateCounts'] is None
 assert 'hostId' not in result

@pytest.mark.parametrize('rows', [[],[{'org_id':'dev-org','project_id':'dev-project','assignment_revision':1}],[{'org_id':'org-org','project_id':'other','assignment_revision':1}], [{'org_id':'org-org','project_id':'dev-project','assignment_revision':1}]*2])
def test_wrong_missing_or_duplicate_scope_rejected_without_inventory_read(gate,rows):
 with pytest.raises(gate.HostPreflightBlocked):gate.require_restored_preparation_directory(Directory(rows),initial_report=report(),read_report=lambda:pytest.fail('inventory read after invalid directory'))

@pytest.mark.parametrize('changed',[report(1),report(True),report(cluster='other'),{'identity':report()['identity'],'inventory':{}}])
def test_inventory_binding_or_physical_drift_rejected(gate,changed):
 d=Directory([{'org_id':'org-org','project_id':'dev-project','assignment_revision':1}])
 with pytest.raises(gate.HostPreflightBlocked):gate.require_restored_preparation_directory(d,initial_report=report(),read_report=lambda:changed)
