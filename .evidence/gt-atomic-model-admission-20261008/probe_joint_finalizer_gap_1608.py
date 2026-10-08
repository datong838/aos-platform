"""Inspect original producer surface and unconditional actual commit gate."""
import json,hashlib
from pathlib import Path
from aos_api import aip_physical_capacity_occupation_authority as a
B=Path(__file__).resolve().parent
statements='\n'.join(a.occupation_parent_debit_statements()) if hasattr(a,'occupation_parent_debit_statements') else ''
# The actual module text is evidence rather than a substitute for a PG test.
source=Path(a.__file__).read_text()
proof=json.loads((B/'newjudge-source-proof-1607.json').read_text())
rows=json.loads((B.parent/'gt-newjudge-intent-native-20261009/native-r3-independent.json').read_text())
result={'authority_revision':'AOS-001608','module_sha256':hashlib.sha256(source.encode()).hexdigest(),'joint_finalizer_compiler_present':hasattr(a,'occupation_joint_finalizer_statements'),'commit_rejection_implemented':'CAPACITY_PARENT_FINALIZE_REQUIRED' in source,'actual_caller_transaction':rows['newjudge_transaction'],'actual_transaction_status':rows['transaction_status'],'prepared_rows':rows['private_prepared_rows'],'current_prepared_judge_state':'awaiting_target_result','source_purpose':proof['original_fact']['purpose'],'no_database_write':True,'execution_allowed':False,'natural_firstchain':False}
(B/'joint-finalizer-gap-1608.json').write_text(json.dumps(result,indent=2)+'\n')
assert result['joint_finalizer_compiler_present'],'joint finalizer producer absent; actual native caller COMMIT rejected and xid aborted, pending Intent cannot grant execution'
