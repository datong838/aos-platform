"""New approved no-expected Suite/Contract, never modify old originals."""
import hashlib

EXPECTED_BYTES = '  原Judge期望🙂\n保留空白  '.encode('utf-8')

def install(monkeypatch):
    from tests.aip import test_model_eval_request_pg as original
    register = original._register_original_model_eval_contract
    def registered(scope, target, suffix):
        from aos_api.db import connect
        from aos_api.aip_contracts import ArtifactRef
        from aos_api.aip_eval_pack_registry import AipEvalPackRegistry, compute_eval_suite_hash
        from aos_api.aip_production_contract_store import AipProductionContractStore
        from aos_api.aip_production_contracts import CreateEvalContractRequest
        old, contract = register(scope, target, suffix)
        artifact = 'judge-no-expected-' + suffix
        suite = old.model_copy(update={'suite_id': artifact+'-suite',
            'cases': [case.model_copy(update={'expected_artifact': None}) for case in old.cases]})
        suite = suite.model_copy(update={'content_hash': compute_eval_suite_hash(suite)})
        AipEvalPackRegistry().register_suite_revision(scope, suite, actor='test-maker')
        store = AipProductionContractStore()
        prior = store.get_eval_contract(scope, contract.contract_id, contract.revision)
        body = CreateEvalContractRequest(**{k:getattr(prior,k) for k in CreateEvalContractRequest.model_fields})
        body = body.model_copy(update={'suite_ref': type(prior.suite_ref)(resource_type='EvalSuiteRevision',
            resource_id=suite.suite_id, revision=suite.revision, content_hash=suite.content_hash)})
        draft = store.create_eval_contract(scope, 'test-maker', 'no-expected-contract-'+suffix, body)
        frozen = store.freeze_eval_contract(scope, 'test-maker', draft.contract_id, draft.version, 'no-expected-freeze-'+suffix)
        return suite, frozen
    monkeypatch.setattr(original, '_register_original_model_eval_contract', registered)
