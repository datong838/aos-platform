"""Prepare a new mapping successor and actual static evaluation, never publish it."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone

import yaml

ROOT=Path(__file__).resolve().parents[1]
CANDIDATES=ROOT/'bundles/candidates/ecommerce'
SOURCE=Path('platform.ecommerce.niushop/1.3.0')
TARGET=Path('platform.ecommerce.niushop/1.4.0')
BASE_HASH='sha256:f79374cef9fbd6c5a55e312b1e18f4bdaeabecb756d95128d82fc8eda28c73bd'
DECLARATION='''
snapshot_materialization:
  schema_version: aos.snapshot-materialization/v1
  platform: niushop
  shop_key: site_id
  source_timezone: "+08:00"
  property_defaults:
    status: active
    currency: CNY
    timezone: "+08:00"
'''


def builder():
    spec=importlib.util.spec_from_file_location('niushop_candidate_prepare_builder',ROOT/'scripts/build_ecommerce_runtime_candidates.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def evaluate(root):
    sys.path.insert(0,str(ROOT/'services/aos-api'))
    from aos_api.pipeline_source_selection import derive_mapping_read_spec
    from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping,materialize_snapshot
    from aos_api.ec_ot_writer import _normalize_rows
    from aos_api.ecom_core_models import SyncScope
    path=root/'content/mappings/p01-shop.yaml'
    mapping=yaml.safe_load(path.read_text())
    schema=json.loads((root/'content/schemas/niushop-schema-fingerprint.json').read_text())
    masking=yaml.safe_load((root/'content/mappings/_pii-exclusion.yaml').read_text())
    read_spec=derive_mapping_read_spec(mapping,schema,masking)
    compiled=compile_snapshot_mapping(mapping,read_spec)
    checks=['pinned-source-schema-privacy-and-materialization-compile']
    raw={field['source']:(1 if field['type']=='int' else 0 if field['type']=='timestamp' else 'synthetic') for field in mapping['field_mappings']}
    at=datetime(2026,9,12,tzinfo=timezone.utc)
    output=materialize_snapshot([raw],compiled,observed_at=at)
    scope=SyncScope(org_id='org-org',workspace_id='dev-project',platform=compiled.platform,shop_or_marketplace_id=compiled.shop_id,stream='P01-shop-qyh')
    objects,links=_normalize_rows(output,scope)
    if len(objects)!=1 or links or len(objects[0].properties)!=14 or objects[0].identity.external_id!='niushop:1:1':
        raise ValueError('candidate canonical object evaluation failed')
    checks.append('fourteen-declared-properties-enter-existing-object-kernel')
    if output[0]['properties']['createTime'] is not None or output[0]['source_updated_at']!=at:
        raise ValueError('candidate observation evaluation failed')
    checks.append('zero-source-time-and-explicit-observation')
    for name,rows in [('pii-extra-column',[raw|{'site_tel':'synthetic'}]),('wrong-shop',[raw|{'site_id':2}]),('duplicate-source-key',[raw,dict(raw)])]:
        try:materialize_snapshot(rows,compiled,observed_at=at)
        except ValueError:checks.append(name+'-rejected')
        else:raise ValueError('candidate negative evaluation failed')
    return dict(status='passed',failed=0,scope='static-snapshot-mapping-only',checks=checks,
        mappingHash='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest())


def prepare():
    source,target=CANDIDATES/SOURCE,CANDIDATES/TARGET
    if target.exists():raise ValueError('immutable candidate target already exists')
    helper=builder()
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable candidate baseline differs')
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    evidence=target/'evidence/bundle-evals.json'
    evidence.write_text(json.dumps(dict(status='pending',failed=0,scope='static-snapshot-mapping-only'))+'\n')
    manifest=target/'bundle.yaml';text=manifest.read_text();marker='  version: 1.3.0\n'
    if text.count(marker)!=1:raise ValueError('candidate version declaration differs')
    manifest.write_text(text.replace(marker,'  version: 1.4.0\n',1))
    mapping=target/'content/mappings/p01-shop.yaml'
    mapping.write_text(mapping.read_text()+DECLARATION)
    evaluation=evaluate(target)
    evidence.write_text(json.dumps(evaluation,sort_keys=True,separators=(',',':'))+'\n')
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable source changed during preparation')
    changed=sorted(str(path.relative_to(source)) for path in source.rglob('*') if path.is_file() and '__pycache__' not in path.parts
        and path.suffix!='.pyc' and path.read_bytes()!=(target/path.relative_to(source)).read_bytes())
    if changed!=['bundle.yaml','content/mappings/p01-shop.yaml','evidence/bundle-evals.json']:
        raise ValueError('unexpected successor changes')
    return dict(outcome='NIUSHOP_SNAPSHOT_CANDIDATE_PREPARED',sourceTreeHash=BASE_HASH,targetTreeHash=helper._tree_hash(target),
        changedFiles=changed,evaluation=evaluation,published=False,installed=False)


if __name__=='__main__':
    print(json.dumps(prepare(),ensure_ascii=False,indent=2))
