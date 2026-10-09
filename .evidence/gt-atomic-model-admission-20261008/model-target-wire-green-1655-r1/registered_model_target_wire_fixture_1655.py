"""New wire policy frozen before original Model request approval, test only."""
def install(monkeypatch, variant):
    from tests.aip import test_model_eval_request_pg as original
    register = original._register_original_model_eval_contract
    def registered(scope, target, suffix):
        from aos_api.aip_production_contract_store import AipProductionContractStore
        from aos_api.aip_production_contracts import CreateEvalContractRequest
        suite, old = register(scope, target, suffix)
        store = AipProductionContractStore()
        prior = store.get_eval_contract(scope, old.contract_id, old.revision)
        wire = {'schemaVersion': 'aos.model-eval.chat-json-target/v1', 'codec': 'httpx-json-v1',
                'role': 'user', 'outputLimitField': 'max_tokens'}
        if variant == 'role': wire['role'] = 'system'
        if variant == 'version': wire['schemaVersion'] = 'aos.model-eval.chat-json-target/v2'
        if variant == 'extra': wire['system'] = 'unapproved'
        gp = dict(prior.gate_policy)
        if variant != 'missing': gp['modelTargetWireFormat'] = wire
        body = CreateEvalContractRequest(**{k: getattr(prior, k) for k in CreateEvalContractRequest.model_fields})
        body = body.model_copy(update={'gate_policy': gp})
        draft = store.create_eval_contract(scope, 'test-maker', 'wire-contract-' + suffix, body)
        frozen = store.freeze_eval_contract(scope, 'test-maker', draft.contract_id, draft.version, 'wire-freeze-' + suffix)
        return suite, frozen
    monkeypatch.setattr(original, '_register_original_model_eval_contract', registered)
