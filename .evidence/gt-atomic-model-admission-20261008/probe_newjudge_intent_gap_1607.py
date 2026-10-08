"""Registered next-wave RED using the actual installed compiler surface."""
import json,hashlib
from pathlib import Path
from aos_api import aip_physical_capacity_occupation_authority as authority
B=Path(__file__).resolve().parent
old='\n'.join(authority.occupation_intent_statements())
assert "CHECK(purpose='target')" in old
assert 'capacity_occupation_eval_case_fact' in old
proof=json.loads((B/'source-newjudge-native-positive-1606.json').read_text())
assert proof['original_fact']['purpose']=='model-judge-call'
result={'old_intent_compiler_sha256':hashlib.sha256(old.encode()).hexdigest(),
 'old_Intent_target_only':True,'actual_newJudge_purpose':'model-judge-call',
 'case_fields':sorted(proof['original_fact']['application']['cases'][0]),
 'newJudge_Intent_producer_present':hasattr(authority,'occupation_judge_intent_statements'),
 'no_database_write':True,'no_fake_target_output':True,'business_firstchain':False}
(B/'newjudge-intent-gap-1607.json').write_text(json.dumps(result,indent=2)+'\n')
assert result['newJudge_Intent_producer_present'],'original newJudge own-parent/input dependency Intent producer is absent; target-only compiler cannot authorize it'
