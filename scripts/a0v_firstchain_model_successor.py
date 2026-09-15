"""Model-only graph successor through the versioned LogicGraph owner.

Callers provide exact historical and target builders; this module never selects
latest revisions, modifies historical rows, or replays an uncertain mutation.
"""
from copy import deepcopy
from aos_api.aip_logic_graph_models import ReplaceLogicGraphRequest, logic_graph_content_payload


def replacement(current, old_request, new_request):
    if not current.id == old_request.id == new_request.id:
        raise ValueError('exact graph identity required')
    old = logic_graph_content_payload(old_request)
    target = logic_graph_content_payload(new_request)
    actual = current.model_dump(mode='json', include=set(old))
    if actual != old:
        raise ValueError('historical graph content drift requires review')
    normalized = deepcopy(target)
    changes = 0
    for node, previous in zip(normalized['nodes'], old['nodes']):
        if node['id'] != previous['id'] or node['kind'] != previous['kind']:
            raise ValueError('graph structure changed')
        if node['kind'] == 'use_llm':
            model = node['config'].get('model')
            before = previous['config'].get('model')
            if not isinstance(model, str) or not model.strip() or not before:
                raise ValueError('exact model alias required')
            changes += model != before
            node['config']['model'] = before
    if normalized != old or not changes:
        raise ValueError('only a nonempty model replacement is allowed')
    return ReplaceLogicGraphRequest(expected_revision=current.revision, **target)


def apply_graph(store, scope, actor, current, request, intent):
    if intent.exists():
        raise ValueError('existing graph intent requires read-only receipt inspection')
    from a0v_qyh_current_product_event_first_chain import freeze
    freeze(intent, dict(graphId=current.id, previousHash=current.graph_hash,
        request=request.model_dump(mode='json', by_alias=True)))
    result = store.replace(*scope.key, current.id, actor, request)
    expected = logic_graph_content_payload(request)
    if result.revision != current.revision + 1 or result.model_dump(mode='json', include=set(expected)) != expected:
        raise ValueError('successor verification failed; inspect history without resend')
    freeze(intent.with_name(intent.stem+'-result.json'),result.model_dump(mode='json',by_alias=True))
    return result
