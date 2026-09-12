"""Owner input and graph checks; these fixtures confer no real approval."""
from copy import deepcopy

import pytest

from aos_api.pipeline_source_selection import MappingReadSpec
from aos_api.pipeline_source_selection_owner import PipelineSourceSelectionOwner, verify_graph_read_spec


def graph_case():
    mappings = [{'source':'site_id','target':'siteId'}, {'source':'site_name','target':'name'}]
    graph = {'pipeline_id':'p01','write_mode':'SNAPSHOT','nodes':[
        {'id':'s','node_type':'source','config':{'source_id':'source','source_table':'ns_site',
            'pk':'site_id','site_filter':'site_id=1','incremental_strategy':'snapshot','initial':False}},
        {'id':'t','node_type':'transform','config':{'field_mappings':deepcopy(mappings),'target_ot':'Shop','expression':'row'}},
        {'id':'o','node_type':'sink','config':{'target_ot':'Shop','write_mode':'SNAPSHOT'}},
    ],'edges':[{'source_node_id':'s','target_node_id':'t'},{'source_node_id':'t','target_node_id':'o'}]}
    return graph, {'field_mappings':mappings}, MappingReadSpec('ns_site','Shop','site_id',('site_id','site_name'),(('site_id',1),))


def test_owner_cannot_be_composed_from_caller_callbacks():
    with pytest.raises(TypeError):
        PipelineSourceSelectionOwner(installation_store=object(), artifacts=object(), release_policy=object())


def test_graph_matches_pinned_read_spec():
    graph, mapping, spec = graph_case()
    verify_graph_read_spec(graph, mapping, spec, source_id='source')


@pytest.mark.parametrize('case', ['source','table','pk','scope','cursor','initial','strategy','expression','fields','object','mode','edge','extra_node'])
def test_graph_cannot_silently_override_selected_assets(case):
    graph, mapping, spec = graph_case()
    source, transform, sink = [node['config'] for node in graph['nodes']]
    if case == 'source': source['source_id'] = 'other'
    elif case == 'table': source['table'] = 'another_table'
    elif case == 'pk': source['pk'] = 'another_id'
    elif case == 'scope': source['site_filter'] = 'site_id=2'
    elif case == 'cursor': source['cursor'] = {'watermark':1}
    elif case == 'initial': source['initial'] = 'false'
    elif case == 'strategy': source['incremental_strategy'] = 'incremental'
    elif case == 'expression': transform['expression'] = 'custom-code'
    elif case == 'fields': transform['field_mappings'][1]['source'] = 'site_tel'
    elif case == 'object': sink['target_ot'] = 'Other'
    elif case == 'mode': graph['write_mode'] = 'DELETE'
    elif case == 'edge': graph['edges'][1]['target_node_id'] = 's'
    else: graph['nodes'].append({'id':'extra','node_type':'llm','config':{}})
    with pytest.raises(ValueError):
        verify_graph_read_spec(graph, mapping, spec, source_id='source')


@pytest.fixture
def composed_case(monkeypatch):
    """Control-flow seam only; real current authority has separate PG tests."""
    import hashlib
    import json
    from datetime import timedelta
    from types import SimpleNamespace as NS
    import aos_api.pipeline_source_selection_owner as module
    from tests.test_pipeline_runtime_control_contracts import payload
    from tests.test_pipeline_source_selection import assets
    from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft
    from aos_api.tenant_scope import TenantScope
    body = payload(); body.pop('sourceSelectionRef')
    documents = assets()
    paths = ['content/mappings/p01.yaml','content/schemas/schema.json','content/mappings/privacy.yaml']
    raw = {path:json.dumps(doc).encode() for path,doc in zip(paths,documents)}
    for name,path in zip(('mappingRef','schemaRef','maskingPolicyRef'),paths):
        body[name].update(resourceId=path,revision='1.3.0',contentHash='sha256:'+hashlib.sha256(raw[path]).hexdigest())
    draft = PipelineSourceSelectionDraft.model_validate(body)
    graph,_,_ = graph_case()
    graph['nodes'][0]['config']['source_id'] = draft.source_id
    graph['nodes'][1]['config']['field_mappings'] = documents[0]['field_mappings']
    selected = NS(**draft.package_ref.model_dump(),signature_fingerprint='test-signature',release_evidence_revision='test-evidence')
    baseline = NS(lock=NS(payload=NS(resolved=[selected])))
    state = dict(now=draft.not_before+timedelta(minutes=1), config=module._wire(draft.configuration_ref), calls=[])
    class Result:
        def __init__(self,value): self.value=value
        def fetchone(self): return self.value
    class Connection:
        def execute(self,sql,params=()):
            if 'clock_timestamp' in sql: return Result({'now':state['now']})
            if 'config_ref FROM' in sql: return Result({'config_ref':state['config']})
            if 'SELECT payload FROM' in sql: return Result({'payload':graph})
            raise AssertionError(sql)
    owner = object.__new__(PipelineSourceSelectionOwner)
    owner._store = NS(load_active_baseline_in_transaction=lambda *a,**kw:baseline)
    owner._authorization = object()
    from pathlib import Path
    import yaml
    from aos_api.asset_registry.contracts import BundleManifest
    manifest = BundleManifest.model_validate(yaml.safe_load((Path(__file__).resolve().parents[3] / 'bundles/platforms/ecommerce-niushop/bundle.yaml').read_text()))
    owner._artifacts = NS(scope=TenantScope(draft.org_id,draft.project_id),
        load_record=lambda item:NS(manifest=manifest),
        read_artifact=lambda item,path,limit:raw[path])
    owner._release_policy = NS(evaluate=lambda *a,**kw:state['calls'].append('release'))
    def current_config(*a,**kw):
        state['calls'].append('configuration')
        if state.get('deny'): raise PermissionError('current authority denied')
    monkeypatch.setattr(module,'read_configuration',current_config)
    monkeypatch.setattr(module.IngressJournal,'verify_pipeline_source_binding',lambda *a,**kw:state['calls'].append('graph'))
    monkeypatch.setattr(module.SourceConfigurationRevisionStore,'read_current',lambda *a:NS(ref=draft.source_configuration_ref))
    def gate(db,**kw):
        kw['check_current_policy'](db,baseline)
        return kw['execute']()
    monkeypatch.setattr(module,'run_guarded',gate)
    return owner,Connection(),draft,state,raw


def test_owner_rechecks_configuration_after_verified_asset_reads(composed_case):
    owner,conn,draft,state,_ = composed_case
    spec = owner._guarded(conn,draft,'actor',lambda value:value)
    assert spec.table == 'ns_site' and len(spec.columns) == 11
    assert state['calls'] == ['configuration','graph','release','configuration']


@pytest.mark.parametrize('mode',['config','authority','expired','asset_hash','asset_path','asset_revision','scope','source'])
def test_composed_denial_never_reaches_append(composed_case,monkeypatch,mode):
    from aos_api.tenant_scope import TenantScope
    from aos_api.source_configuration_revision import SourceConfigurationRevisionStore
    owner,conn,draft,state,raw = composed_case
    if mode == 'config': state['config'] = {}
    elif mode == 'authority': state['deny'] = True
    elif mode == 'expired': state['now'] = draft.expires_at
    elif mode == 'asset_hash': raw[draft.mapping_ref.resource_id] += b' '
    elif mode == 'asset_path': draft = draft.model_copy(update={'mapping_ref':draft.mapping_ref.model_copy(update={'resource_id':'private.yaml'})})
    elif mode == 'asset_revision': draft = draft.model_copy(update={'mapping_ref':draft.mapping_ref.model_copy(update={'revision':'1.2.0'})})
    elif mode == 'scope': owner._artifacts.scope = TenantScope('dev-org','dev-project')
    else: monkeypatch.setattr(SourceConfigurationRevisionStore,'read_current',lambda *a:None)
    with pytest.raises((PermissionError,ValueError)):
        owner._guarded(conn,draft,'actor',lambda value:pytest.fail('denied request appended'))
