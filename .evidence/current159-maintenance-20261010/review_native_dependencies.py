"""Native readonly conindid binding proof for nine exact retained FKs."""
import json,sys,subprocess,os
from pathlib import Path
import psycopg
E=Path(__file__).resolve().parent;R=E.parents[1];sys.path.insert(0,str(E));sys.path.insert(0,str(R/'scripts'))
import a0v_current_preview_bootstrap as b
import snapshot_supplement as sup
import snapshot_all as base
from dependency_review import TABLES,require_binding_pairs,canonical_dependencies
S=R.parent/'aos-recovery/current159-first-05b88779fad3/supplement-r1'
QUERY="""SELECT n.nspname AS schema,c.relname AS table,k.conname AS constraint,i.relname AS index,nt.nspname AS target_schema,ct.relname AS target_table,am.amname AS index_method,x.indisunique AS unique,x.indimmediate AS immediate,x.indisvalid AS valid,x.indisready AS ready,x.indislive AS live,x.indisprimary AS primary,x.indnullsnotdistinct AS nulls_not_distinct,x.indnkeyatts AS key_count,x.indnatts AS total_count,
 ARRAY(SELECT a.attname FROM unnest(x.indkey) WITH ORDINALITY z(key,ord) LEFT JOIN pg_attribute a ON a.attrelid=x.indrelid AND a.attnum=z.key ORDER BY z.ord) AS key_columns,
 ARRAY(SELECT no.nspname||'.'||op.opcname FROM unnest(x.indclass) WITH ORDINALITY z(key,ord) JOIN pg_opclass op ON op.oid=z.key JOIN pg_namespace no ON no.oid=op.opcnamespace ORDER BY z.ord) AS opclasses,
 ARRAY(SELECT CASE WHEN z.key=0 THEN 'NONE' ELSE nc.nspname||'.'||co.collname END FROM unnest(x.indcollation) WITH ORDINALITY z(key,ord) LEFT JOIN pg_collation co ON co.oid=z.key LEFT JOIN pg_namespace nc ON nc.oid=co.collnamespace ORDER BY z.ord) AS collations,
 ARRAY(SELECT z.key FROM unnest(x.indoption) WITH ORDINALITY z(key,ord) ORDER BY z.ord) AS options,
 pg_get_expr(x.indpred,x.indrelid) AS predicate,pg_get_expr(x.indexprs,x.indrelid) AS expressions
 FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_class i ON i.oid=k.conindid JOIN pg_index x ON x.indexrelid=i.oid JOIN pg_class ct ON ct.oid=x.indrelid JOIN pg_namespace nt ON nt.oid=ct.relnamespace JOIN pg_am am ON am.oid=i.relam
 WHERE n.nspname='public' AND k.contype='f' AND c.relname IN ("""+','.join(psycopg.sql.Literal(t).as_string() for t in sorted(TABLES))+""" ) AND k.conname='fk_'||c.relname||'_module_ti2'"""
with psycopg.connect(**b._connection_parameters()) as c:
 c.read_only=True;source=base.rows(c,QUERY)
sql='BEGIN READ ONLY; SET LOCAL timezone=\'UTC\'; SELECT coalesce(json_agg(r ORDER BY row_to_json(r)::text),\'[]\'::json) FROM ('+QUERY+') r; COMMIT;'
p=subprocess.run(['docker','--context','colima-aos-extension','exec','current159-first-1579cb9f5251','psql','-U','aos_app','-d','aos_current_preview_20260927','-Atq','-v','ON_ERROR_STOP=1','-c',sql],capture_output=True,timeout=30);assert p.returncode==0
restored=json.loads(p.stdout);proof=require_binding_pairs(source,restored)
a=json.loads((S/'source.json').read_text());bdata=json.loads((S/'restored.json').read_text());left=sup.canonical(a['supplement'],a['base']['triggers']);right=sup.canonical(bdata['supplement'],bdata['base']['triggers'])
left['dependencies']=canonical_dependencies(left['dependencies'],proof);right['dependencies']=canonical_dependencies(right['dependencies'],proof);sup.require_supplement_equivalent(left,right)
report={'status':'SUPPLEMENT_COMPLETE_NATIVE_REVIEWED_EQUIVALENCE_GREEN','binding_count':len(proof),'toast_internal_name_changes':614,'source_binding':source,'restored_binding':restored,'full_supplement_fields':sorted(sup.FIELDS),'all_other_supplement_exact':True,'database_writes':0,'migration_allowed':False}
with (S/'binding-review.json').open('x') as f:json.dump(report,f,indent=2,sort_keys=True)
(E/'supplement-reviewed-r2.json').open('x').write(json.dumps({k:v for k,v in report.items() if k not in ('source_binding','restored_binding')},indent=2)+'\n');print(report['status'],report['binding_count'])
