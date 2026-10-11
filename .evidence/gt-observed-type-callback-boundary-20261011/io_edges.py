import hashlib,json
from pathlib import Path
B=Path(__file__).resolve().parent;R=B.parents[1]
prior=R/'.evidence/gt-expression-types-transient-catalog-20261011/r5'
x=json.loads((B/'result.json').read_text());records=json.loads((prior/'typed-records.json').read_text())
types={t['oid']:t for t in x['types']};funcs={f['oid']:f for f in x['typeCallbackFunctions']};observed=set(x['observerFunctionOids'])
# The reviewed probe emits InvalidOid (0) for CoerceViaIO; preserve the numeric tag as evidence.
probe=R/'.evidence/gt-fixed-validator-expression-types-20261011/probe.c'
assert 'IsA(node, CoerceViaIO)' in probe.read_text() and 'observe_expression_types(node, InvalidOid, list_make1(coerce->arg), false)' in probe.read_text()
edges=[]
for record in records:
 if record[1]!=0:continue
 assert record[1]==0 and len(record)==4
 result_type,arg_type=record[2:]
 for kind,source_type in [('typoutput',arg_type),('typinput',result_type)]:
  assert source_type in types
  fid=types[source_type]['callbacks'][kind];assert fid and fid in funcs
  edges.append({'record':record,'kind':kind,'sourceTypeOid':source_type,'functionOid':fid,'signature':funcs[fid]['signature'],'functionSourceHash':funcs[fid]['sourceHash'],'recordedByPlannerObserver':fid in observed,'actualNativeCallProven':False})
paths=['src/backend/executor/execExpr.c','src/backend/executor/execExprInterp.c','src/backend/utils/adt/arrayfuncs.c'];source=R/'.evidence/gt-shared-parent-native-ending-20261011/backend-source-audit-r1/source'
result={'coerceViaIORecordCount':len(edges)//2,'ioCatalogEdges':edges,'probeSourceSha256':hashlib.sha256(probe.read_bytes()).hexdigest(),'localBackendSourceHashes':{p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in paths},'sourceReview':['execExpr.c resolves source typoutput and destination typinput with getTypeOutputInfo/getTypeInputInfo and fmgr_info','arrayfuncs.c obtains element input/output/receive/send via get_type_io_data'],'runtimeBinarySourceIdentityProvenByThisAudit':False,'actualNativeEventCoverageProven':False,'executionAuthorized':False}
(B/'io-callback-edges.json').open('x').write(json.dumps(result,indent=2)+'\n');print(json.dumps({'coerceViaIORecords':result['coerceViaIORecordCount'],'potentialIoFunctions':len({e['functionOid'] for e in edges}),'potentialIoFunctionsNotRecorded':len({e['functionOid'] for e in edges if not e['recordedByPlannerObserver']}),'actualNativeEventsProven':False}))
