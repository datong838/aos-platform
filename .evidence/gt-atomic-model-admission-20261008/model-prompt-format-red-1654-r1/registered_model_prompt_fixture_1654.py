"""New original prompt Dataset/Suite/Contract, never a Model quality grant."""
import hashlib
import json
from datetime import datetime, timezone

SCHEMA = {'type': 'object', 'properties': {'prompt': {'type': 'string', 'minLength': 1}},
          'required': ['prompt'], 'additionalProperties': False}

def raw_json(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')

def policy():
    from aos_api.aip_budget_reservation_store import canonical_hash
    return {'schemaVersion': 'aos.model-eval.single-user-prompt/v1',
            'inputSchemaHash': canonical_hash(SCHEMA), 'renderer': 'aos.model-eval.single-user-prompt/v1'}

def install(monkeypatch, variant):
    from tests.aip import test_model_eval_request_pg as original
    register = original._register_original_model_eval_contract
    values = {'valid': {'prompt': '  原模型输入🙂\n保持空白  '}, 'extra': {'prompt': 'x', 'system': 'hidden'},
              'missing': {'caseId': 'x'}, 'number': {'prompt': 3}, 'empty': {'prompt': ''},
              'whitespace': {'prompt': '\t \n'}, 'surrogate': {'prompt': '\ud800'},
              'version': {'prompt': 'x'}, 'no-policy': {'prompt': 'x'}}
    value = values[variant]
    global TEST_VALUE
    TEST_VALUE = value
    encoded = raw_json(value)
    input_hash = hashlib.sha256(encoded).hexdigest()

    def registered(scope, target, suffix):
        from aos_api.db import connect
        from aos_api.aip_budget_reservation_store import canonical_hash
        from aos_api.aip_contracts import ArtifactRef
        from aos_api.aip_eval_contracts import (DatasetRevisionRef, EvalDatasetManifest, DatasetSourceKind,
            DatasetPiiState, AssetRevisionRef, AssetType, EvalCaseDefinition, EvalCaseKind, EvalSuiteRevision)
        from aos_api.aip_eval_pack_registry import AipEvalPackRegistry, compute_eval_suite_hash
        from aos_api.aip_production_contract_store import AipProductionContractStore
        from aos_api.aip_production_contracts import CreateEvalContractRequest
        # Retain original governance publication; new prompt inputs get their own
        # source/receipt/Dataset/Suite/Contract before the original approval action.
        old_suite, old_contract = register(scope, target, suffix)
        store = AipProductionContractStore()
        prior = store.get_eval_contract(scope, old_contract.contract_id, old_contract.revision)
        prefix = 'model-prompt-' + suffix
        source_hash = canonical_hash({'schemaVersion': 'aos.isolated-model-prompt-source/v1',
            'inputHash': input_hash, 'caseId': 'prompt-only'})
        receipt_hash = canonical_hash({'sourceHash': source_hash, 'piiState': 'none', 'testOnly': True})
        dataset = DatasetRevisionRef(dataset_id=prefix + '-dataset', revision=1,
            content_hash=canonical_hash({'sourceHash': source_hash, 'caseCount': 1}), source_hash=source_hash,
            redaction_policy=AssetRevisionRef(asset_type=AssetType.POLICY,
                asset_id='isolated-model-prompt-no-pii-v1', revision='1', content_hash=canonical_hash('isolated-no-pii-v1')))
        manifest = EvalDatasetManifest(source_kind=DatasetSourceKind.ARTIFACT_SNAPSHOT,
            source_id=prefix + '-source', source_revision='1', source_hash=source_hash, fields_allowlist=['prompt'],
            redaction_receipt=ArtifactRef(artifact_id=prefix + '-redaction', artifact_type='redaction_receipt',
                revision='1', content_hash=receipt_hash), pii_state=DatasetPiiState.NONE, case_count=1,
            captured_at=datetime.now(timezone.utc))
        with connect(scope) as c:
            for aid, kind, digest, src in ((manifest.source_id, 'eval_dataset_snapshot', source_hash, {}),
                    (manifest.redaction_receipt.artifact_id, 'redaction_receipt', receipt_hash,
                     {'sourceArtifactRef': {'artifactId': manifest.source_id, 'artifactType': 'eval_dataset_snapshot',
                         'revision': '1', 'contentHash': source_hash}})):
                c.execute("INSERT INTO aip_artifact (org_id,project_id,artifact_id,artifact_type,content_hash,content_ref,source,created_by) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,'test-maker')",
                          (*scope.key, aid, kind, digest, 'test-only://' + aid, json.dumps(src)))
            c.commit()
        registry = AipEvalPackRegistry()
        registry.register_dataset_revision(scope, dataset, manifest, actor='test-maker')
        suite = EvalSuiteRevision(suite_id=prefix + '-suite', revision=1, content_hash='0' * 64,
            target=target, dataset=dataset, judge=old_suite.judge,
            cases=[EvalCaseDefinition(case_id='prompt-only', kind=EvalCaseKind.BOUNDARY,
                input_artifact=ArtifactRef(artifact_id=prefix + '-input', artifact_type='eval_input', revision='1',
                    content_hash=input_hash), timeout_ms=1000)], gate_threshold=1.0)
        suite = suite.model_copy(update={'content_hash': compute_eval_suite_hash(suite)})
        registry.register_suite_revision(scope, suite, actor='test-maker')
        format_policy = policy()
        if variant == 'version': format_policy['schemaVersion'] = 'aos.model-eval.single-user-prompt/v2'
        gp = {'subjectKind': 'model_eval', 'executionAllowed': False}
        if variant != 'no-policy': gp['modelInputFormat'] = format_policy
        body = CreateEvalContractRequest(suiteRef={'resourceType': 'EvalSuiteRevision', 'resourceId': suite.suite_id,
            'revision': 1, 'contentHash': suite.content_hash}, publicationRef=prior.publication_ref,
            releaseGateRef=prior.release_gate_ref, artifactSchemaRef=prior.artifact_schema_ref,
            severityThresholds=prior.severity_thresholds, gatePolicy=gp, returnMapping=prior.return_mapping,
            overridePolicy=prior.override_policy)
        draft = store.create_eval_contract(scope, 'test-maker', prefix + '-contract', body)
        frozen = store.freeze_eval_contract(scope, 'test-maker', draft.contract_id, draft.version, prefix + '-freeze')
        return suite, frozen

    monkeypatch.setattr(original, '_register_original_model_eval_contract', registered)
    return encoded
