"""Compare complete original Docker resource metadata, mount multiset only."""
import copy,json
def require_same(before,after):
 def normalized(value):
  if set(value)!= {'Id','started','mounts','ports'}:raise ValueError('COMPLETE_RESOURCE_METADATA_REQUIRED')
  result=copy.deepcopy(value)
  result['mounts']=sorted(result['mounts'],key=lambda x:json.dumps(x,sort_keys=True))
  return result
 if normalized(before)!=normalized(after):raise ValueError('ORIGINAL_RESOURCE_CHANGED')
 return True
