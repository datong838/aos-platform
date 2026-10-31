"""Server-derived pending Judge-call request on the original caller transaction.

The two quality-eval approvals provide necessary provenance only. This module
does not grant Judge-call approval, reserve funds or admit/dispatch execution.
"""
import json
from uuid import uuid4

import psycopg
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row

from aos_api.aip_action_store import canonical_hash
from aos_api.aip_eval_contracts import AssetType
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry, compute_eval_suite_hash
from aos_api.aip_model_eval_action import ModelEvalActionGuard
from aos_api.aip_model_eval_judge_authorization import ModelJudgeCallRequestInput,ModelJudgeCallRuleRequestInput
from aos_api.auth import Principal
from aos_api.tenant_scope import TenantScope


class ModelJudgeRequestRejected(ValueError):
    pass


class ModelJudgeCallRequestStore:
    def read_published_rule(self,conn: psycopg.Connection,scope: TenantScope,source,
                            *,release_policy,artifact_bytes: dict[str,bytes]) -> dict:
        """Necessary signed rule source, not approval, body-read or Model authority.

        release_policy is an internal service-controlled dependency, not a field
        accepted from request JSON. This never loads or runs implementation code.
        """
        from aos_api.aip_model_eval_judge_authorization import ModelJudgeRuleSourceRef,ModelJudgeRuleDefinition
        from aos_api.asset_registry.registry_store import PostgresRegistryStore
        from aos_api.asset_registry.registry_service import _VersionRecord
        from aos_api.asset_registry.release_policy import ReleasePolicy
        from aos_api.asset_registry.errors import AssetRegistryError
        import hashlib
        self._caller(conn,scope)
        if type(source) is not ModelJudgeRuleSourceRef or type(release_policy) is not ReleasePolicy:
            raise ModelJudgeRequestRejected('JUDGE_ORIGINAL_RULE_SOURCE_REQUIRED')
        try:
            source=ModelJudgeRuleSourceRef.model_validate(source.model_dump(by_alias=True))
        except (TypeError,ValueError) as exc:
            raise ModelJudgeRequestRejected('JUDGE_ORIGINAL_RULE_SOURCE_INVALID') from exc
        artifacts=(source.rule_artifact,source.template_artifact,source.implementation_artifact)
        if type(artifact_bytes) is not dict or set(artifact_bytes)!={a.relative_path for a in artifacts}:
            raise ModelJudgeRequestRejected('JUDGE_EXACT_RULE_ARTIFACT_BYTES_REQUIRED')
        for artifact in artifacts:
            raw=artifact_bytes[artifact.relative_path]
            if (type(raw) is not bytes or len(raw)!=artifact.size
                or 'sha256:'+hashlib.sha256(raw).hexdigest()!=artifact.digest):
                raise ModelJudgeRequestRejected('JUDGE_ORIGINAL_RULE_BYTES_DRIFTED')
        with conn.cursor(row_factory=dict_row) as cur:
            # Use the original registry writer/projection global ordering.
            cur.execute('SELECT pg_advisory_xact_lock(228,1)')
            bundle=cur.execute('SELECT * FROM asset_bundle WHERE publisher=%s AND bundle_id=%s FOR SHARE',
                               (source.publisher,source.bundle_id)).fetchone()
            if bundle is None:
                raise ModelJudgeRequestRejected('JUDGE_PUBLISHED_RULE_BUNDLE_REQUIRED')
            version=cur.execute('SELECT version_pk FROM asset_bundle_version WHERE bundle_pk=%s AND version=%s FOR SHARE',
                                (bundle['bundle_pk'],source.version)).fetchone()
            if version is None:
                raise ModelJudgeRequestRejected('JUDGE_PUBLISHED_RULE_VERSION_REQUIRED')
            try:
                original=PostgresRegistryStore()._load_version(conn,bundle,source.version)
                record=_VersionRecord.from_store(original)
                policy=release_policy.snapshot()
                now=cur.execute('SELECT clock_timestamp() AS now').fetchone()['now']
                result=policy.evaluate(record,checked_at=now,require_published=True)
            except (AssetRegistryError,TypeError,ValueError,RuntimeError) as exc:
                raise ModelJudgeRequestRejected('JUDGE_CURRENT_PUBLISHED_RULE_AUTHORITY_REQUIRED') from exc
            if record.content_hash!=source.content_hash:
                raise ModelJudgeRequestRejected('JUDGE_EXACT_RULE_BUNDLE_HASH_REQUIRED')
            indexed={a['relativePath']:a for a in original['artifacts']}
            if any(indexed.get(a.relative_path)!=a.model_dump(mode='json',by_alias=True) for a in artifacts):
                raise ModelJudgeRequestRejected('JUDGE_SIGNED_RULE_ARTIFACT_INDEX_REQUIRED')
            try:
                raw=artifact_bytes[source.rule_artifact.relative_path]
                definition=ModelJudgeRuleDefinition.model_validate(json.loads(raw.decode('utf-8')))
                rule=definition.model_dump(mode='json',by_alias=True)
                if json.dumps(rule,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()!=raw:
                    raise ValueError('canonical exact rule body required')
            except (TypeError,ValueError) as exc:
                raise ModelJudgeRequestRejected('JUDGE_EXACT_RULE_DEFINITION_REQUIRED') from exc
            if (definition.template_digest!=source.template_artifact.digest
                or definition.implementation_digest!=source.implementation_artifact.digest):
                raise ModelJudgeRequestRejected('JUDGE_RULE_TEMPLATE_IMPLEMENTATION_DRIFTED')
            # Recheck time-sensitive original release inputs after all parsing.
            now=cur.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            try:
                policy.evaluate(record,checked_at=now,require_published=True)
            except (AssetRegistryError,TypeError,ValueError,RuntimeError) as exc:
                raise ModelJudgeRequestRejected('JUDGE_CURRENT_RULE_RELEASE_EXPIRED') from exc
            root=policy._get_trust_root(record)
            from aos_api.asset_registry.release_policy import REQUIRED_RELEASE_EVIDENCE
            windows=[e.expires_at for e in record.evidence if e.type in REQUIRED_RELEASE_EVIDENCE and e.expires_at is not None]
            if root is not None and root.not_after is not None:windows.append(root.not_after)
            valid_until=min(windows) if windows else None
            return {'source':source.model_dump(mode='json',by_alias=True),'rule':rule,
                    'rootRevision':None if root is None else root.revision,
                    'validUntil':None if valid_until is None else valid_until.isoformat(),
                    'ruleHash':canonical_hash(rule),'signatureFingerprint':result.signature_fingerprint,
                    'releaseEvidenceRevision':result.release_evidence_revision,
                    'approvalAllowed':False,'executionAllowed':False}

    @staticmethod
    def _caller(conn: psycopg.Connection, scope: TenantScope) -> None:
        if (type(conn) is not psycopg.Connection or conn.closed
            or conn.info.transaction_status is not TransactionStatus.INTRANS
            or type(scope) is not TenantScope or scope.key!=('org-org','dev-project')):
            raise ModelJudgeRequestRejected('JUDGE_CALLER_INPUT_REQUIRED')
        with conn.cursor(row_factory=dict_row) as cur:
            identity = cur.execute("""SELECT current_user AS role,
              current_setting('aos.org_id',true) AS org_id,
              current_setting('aos.project_id',true) AS project_id,
              current_setting('transaction_isolation') AS isolation""").fetchone()
        if (identity['role'],identity['org_id'],identity['project_id'])!=(
            'aos_runtime',*scope.key,
        ):
            raise ModelJudgeRequestRejected('JUDGE_CALLER_TENANT_REQUIRED')
        if identity['isolation']!='serializable':
            raise ModelJudgeRequestRejected('JUDGE_SERIALIZABLE_CALLER_REQUIRED')

    def _derive(self, conn: psycopg.Connection, scope: TenantScope,
                actor: str, body: ModelJudgeCallRequestInput) -> dict:
        self._caller(conn,scope)
        if (type(actor) is not str or not actor or actor.strip()!=actor
            or type(body) is not ModelJudgeCallRequestInput):
            raise ModelJudgeRequestRejected('JUDGE_CALLER_INPUT_REQUIRED')
        try:
            # Revalidate model_copy inputs as well as ordinary parsed inputs.
            body = ModelJudgeCallRequestInput.model_validate(body.model_dump())
        except (TypeError, ValueError) as exc:
            raise ModelJudgeRequestRejected('JUDGE_INPUT_REQUIRED') from exc
        with conn.cursor(row_factory=dict_row) as cur:
            guard = ModelEvalActionGuard()
            source_ids = [body.target_request_id, body.judge_request_id]
            rows = cur.execute("""SELECT * FROM aip_model_eval_request
              WHERE org_id=%s AND project_id=%s AND request_id=ANY(%s)
              ORDER BY source_ref->>'assetId',request_id""", (*scope.key,source_ids)).fetchall()
            if len(rows)!=2:
                raise ModelJudgeRequestRejected('JUDGE_ORIGINAL_APPLICATION_REQUIRED')
            originals = {}
            expected_hashes = {body.target_request_id:body.target_request_hash,
                               body.judge_request_id:body.judge_request_hash}
            approval_ids = {body.target_request_id:body.target_approval_event_id,
                            body.judge_request_id:body.judge_approval_event_id}
            deadlines = [body.expires_at]
            # Original mutable Model locks are acquired in stable source order.
            # The immutable requests themselves need no extra locking protocol.
            requests = {}
            for row in rows:
                request_id = row['request_id']
                try:
                    request,maker = guard._request(conn,scope,request_id,expected_hashes[request_id])
                except (TypeError,ValueError,RuntimeError) as exc:
                    raise ModelJudgeRequestRejected('JUDGE_ORIGINAL_APPLICATION_DRIFTED') from exc
                if (request.tenant.org_id,request.tenant.project_id)!=scope.key:
                    raise ModelJudgeRequestRejected('JUDGE_ORIGINAL_APPLICATION_TENANT_DRIFTED')
                requests[request_id] = (request,maker)
            for row in rows:
                request_id = row['request_id']
                request,maker = requests[request_id]
                approval = cur.execute("""SELECT * FROM aip_action_approval_event
                  WHERE org_id=%s AND project_id=%s AND approval_event_id=%s""",
                  (*scope.key,approval_ids[request_id])).fetchone()
                proposal = None if approval is None else cur.execute("""SELECT * FROM aip_action_proposal
                  WHERE org_id=%s AND project_id=%s AND proposal_id=%s FOR SHARE""",
                  (*scope.key,approval['proposal_id'])).fetchone()
                if (approval is None or proposal is None or approval['decision']!='approved'
                    or proposal['status']!='approved' or approval['expires_at'] is None
                    or proposal['payload']!={'requestId':request_id,'requestHash':row['request_hash']}
                    or approval['proposal_hash']!=proposal['proposal_hash']
                    or int(approval['proposal_version'])!=int(proposal['version'])-1
                    or approval['action_binding_hash']!=proposal['action_binding_hash']
                    or approval['approval_policy_hash']!=proposal['approval_policy_hash']):
                    raise ModelJudgeRequestRejected('JUDGE_ORIGINAL_APPROVAL_REQUIRED')
                try:
                    guard.check_proposal(conn,scope,approval['actor_id'],proposal,checker=True)
                except (TypeError,ValueError,RuntimeError) as exc:
                    raise ModelJudgeRequestRejected('JUDGE_ORIGINAL_APPROVAL_DRIFTED') from exc
                originals[request_id] = (request,maker,approval,proposal)
                deadlines.extend([request.expires_at,approval['expires_at'],proposal['expires_at']])
            target,maker,_,_ = originals[body.target_request_id]
            judge,_,_,_ = originals[body.judge_request_id]
            if actor!=maker:
                raise ModelJudgeRequestRejected('JUDGE_TARGET_MAKER_REQUIRED')
            try:
                guard._role(conn,scope,maker)
            except (TypeError,ValueError,RuntimeError) as exc:
                raise ModelJudgeRequestRejected('JUDGE_CURRENT_MAKER_REQUIRED') from exc
            ref = target.suite_ref
            suite_row = cur.execute("""SELECT * FROM aip_eval_suite_revision
              WHERE org_id=%s AND project_id=%s AND suite_id=%s AND revision=%s""",
              (*scope.key,ref.asset_id,ref.revision)).fetchone()
            if suite_row is None:
                raise ModelJudgeRequestRejected('JUDGE_TARGET_SUITE_REQUIRED')
            suite = AipEvalPackRegistry._suite_from_row(suite_row)
            route = suite.judge.model_route
            if (suite.content_hash!=ref.content_hash or compute_eval_suite_hash(suite)!=ref.content_hash
                or route is None or route.asset_type is not AssetType.REGISTERED_MODEL
                or (route.asset_id,str(route.revision),route.content_hash)!=(
                    judge.source_ref.asset_id,str(judge.source_ref.revision),judge.source_ref.content_hash)):
                raise ModelJudgeRequestRejected('JUDGE_SUITE_MODEL_BINDING_REQUIRED')
            now = cur.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            if any(deadline<=now for deadline in deadlines) or any(
                body.expires_at>deadline for deadline in deadlines[1:]
            ):
                raise ModelJudgeRequestRejected('JUDGE_CURRENT_EXPIRY_REQUIRED')
            def source(request_id):
                request,_,approval,proposal = originals[request_id]
                return {'requestId':request_id,'requestHash':expected_hashes[request_id],
                        'request':request.model_dump(mode='json',by_alias=True),
                        'approvalEventId':approval['approval_event_id'],
                        'proposalId':proposal['proposal_id'],'proposalHash':proposal['proposal_hash']}
            cases = [case.model_dump(mode='json',by_alias=True) for case in suite.cases]
            payload = {
                'schemaVersion':'aos.model-judge-call-request/v1',
                'tenant':target.tenant.model_dump(mode='json',by_alias=True),
                'purpose':'model-judge-call','executionAllowed':False,'createdBy':maker,
                'targetApplication':source(body.target_request_id),
                'judgeGovernanceApplication':source(body.judge_request_id),
                'suiteRef':ref.model_dump(mode='json',by_alias=True),
                'evalContractRef':target.eval_contract_ref.model_dump(mode='json',by_alias=True),
                'judgeRef':suite.judge.model_dump(mode='json',by_alias=True),
                'cases':cases,'caseSetHash':canonical_hash(cases),
                'currency':'CNY','upperBoundMinor':body.upper_bound_minor,
                'expiresAt':body.expires_at.isoformat(),
            }
            return payload

    def create(self, conn: psycopg.Connection, principal: Principal,
               idempotency_key: str, body: ModelJudgeCallRequestInput) -> dict:
        if (type(principal) is not Principal or principal.token_kind!='oidc'
            or type(idempotency_key) is not str or not idempotency_key
            or len(idempotency_key)>200 or idempotency_key.strip()!=idempotency_key):
            raise ModelJudgeRequestRejected('JUDGE_CALLER_INPUT_REQUIRED')
        scope=TenantScope(principal.org_id,principal.project_id)
        payload=self._derive(conn,scope,principal.subject,body)
        return self._persist(conn,scope,idempotency_key,payload)

    @staticmethod
    def _persist(conn,scope,idempotency_key,payload):
        maker=payload['createdBy']
        # The revalidated server payload also fixes model_copy/coercion inputs.
        from datetime import datetime
        expiry=datetime.fromisoformat(payload['expiresAt'])
        with conn.cursor(row_factory=dict_row) as cur:
            request_hash = canonical_hash(payload)
            prior = cur.execute("""SELECT request_id,request_hash,request_json,created_by,expires_at
              FROM aip_model_eval_judge_request WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
              (*scope.key,idempotency_key)).fetchone()
            if prior is not None:
                if (prior['request_hash']!=request_hash or prior['request_json']!=payload
                    or prior['created_by']!=maker or prior['expires_at']!=expiry):
                    raise ModelJudgeRequestRejected('JUDGE_IDEMPOTENCY_CONFLICT')
                return dict(prior)
            row = cur.execute("""INSERT INTO aip_model_eval_judge_request
              (org_id,project_id,request_id,idempotency_key,request_hash,request_json,created_by,expires_at)
              VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
              RETURNING request_id,request_hash,request_json,created_by,expires_at""",
              (*scope.key,'model-judge-request-'+uuid4().hex,idempotency_key,request_hash,
               json.dumps(payload,ensure_ascii=False),maker,expiry)).fetchone()
            return dict(row)

    def require_current(self, conn: psycopg.Connection, scope: TenantScope,
                        request_id: str, request_hash: str) -> dict:
        """SELECT/lock-only rederivation; this neither creates nor approves.

        Stored maker is an untrusted claim until matched to the original maker
        by _derive. It is not a constructed OIDC authentication identity.
        """
        self._caller(conn,scope)
        import re
        if (type(request_id) is not str or not request_id
            or request_id.strip()!=request_id or type(request_hash) is not str
            or re.fullmatch(r'[0-9a-f]{64}',request_hash) is None):
            raise ModelJudgeRequestRejected('JUDGE_CURRENT_REQUEST_INPUT_REQUIRED')
        with conn.cursor(row_factory=dict_row) as cur:
            row=cur.execute("""SELECT request_id,request_hash,request_json,created_by,expires_at
              FROM aip_model_eval_judge_request WHERE org_id=%s AND project_id=%s AND request_id=%s""",
              (*scope.key,request_id)).fetchone()
        if (row is None or row['request_hash']!=request_hash
            or canonical_hash(row['request_json'])!=request_hash):
            raise ModelJudgeRequestRejected('JUDGE_CURRENT_REQUEST_HASH_REQUIRED')
        try:
            p=row['request_json'];target=p['targetApplication'];judge=p['judgeGovernanceApplication']
            body=ModelJudgeCallRequestInput(
                targetRequestId=target['requestId'],targetRequestHash=target['requestHash'],
                targetApprovalEventId=target['approvalEventId'],
                judgeRequestId=judge['requestId'],judgeRequestHash=judge['requestHash'],
                judgeApprovalEventId=judge['approvalEventId'],
                upperBoundMinor=p['upperBoundMinor'],expiresAt=p['expiresAt'],
            )
        except (KeyError,TypeError,ValueError) as exc:
            raise ModelJudgeRequestRejected('JUDGE_CURRENT_REQUEST_INVALID') from exc
        derived=self._derive(conn,scope,row['created_by'],body)
        if (derived!=p or canonical_hash(derived)!=request_hash
            or body.expires_at!=row['expires_at']):
            raise ModelJudgeRequestRejected('JUDGE_CURRENT_REQUEST_REDERIVATION_DRIFTED')
        return dict(row)


    def _derive_with_rule(self,conn,scope,actor,body,*,release_policy,artifact_bytes):
        from datetime import datetime
        from aos_api.asset_registry.release_policy import ReleasePolicy
        from aos_api.asset_registry.errors import AssetRegistryError
        self._caller(conn,scope)
        if type(body) is not ModelJudgeCallRuleRequestInput or type(release_policy) is not ReleasePolicy:
            raise ModelJudgeRequestRejected('JUDGE_MANDATORY_RULE_INPUT_REQUIRED')
        try:
            body=ModelJudgeCallRuleRequestInput.model_validate(body.model_dump(mode='json',by_alias=True))
            policy=release_policy.snapshot()
        except (AssetRegistryError,TypeError,ValueError,RuntimeError) as exc:
            raise ModelJudgeRequestRejected('JUDGE_MANDATORY_RULE_INPUT_INVALID') from exc
        # Registry ordering precedes the original Model/Suite/approval locks.
        facts=self.read_published_rule(conn,scope,body.rule_source,release_policy=policy,artifact_bytes=artifact_bytes)
        legacy=ModelJudgeCallRequestInput.model_validate(body.model_dump(exclude={'schema_version','rule_source'}))
        payload=self._derive(conn,scope,actor,legacy)
        rule=facts['rule'];ref=payload['judgeRef']
        if ((rule['judgeId'],rule['revision'],facts['ruleHash'])!=(ref['judgeId'],ref['revision'],ref['contentHash'])
            or rule['modelRef']!=payload['judgeGovernanceApplication']['request']['sourceRef']):
            raise ModelJudgeRequestRejected('JUDGE_RULE_SUITE_MODEL_BINDING_REQUIRED')
        # Source locks or membership can wait. Recheck original release time
        # against the same frozen Root snapshot before deriving persistent facts.
        current=self.read_published_rule(conn,scope,body.rule_source,release_policy=policy,artifact_bytes=artifact_bytes)
        if current!=facts:
            raise ModelJudgeRequestRejected('JUDGE_RULE_SOURCE_REDERIVATION_DRIFTED')
        if current['validUntil'] is not None and body.expires_at>datetime.fromisoformat(current['validUntil']):
            raise ModelJudgeRequestRejected('JUDGE_RULE_REQUEST_WINDOW_REQUIRED')
        payload['schemaVersion']='aos.model-judge-call-request/v2'
        payload['ruleFacts']=current
        return payload

    def create_with_rule(self,conn,principal,idempotency_key,body,*,release_policy,artifact_bytes):
        if (type(principal) is not Principal or principal.token_kind!='oidc'
            or type(idempotency_key) is not str or not idempotency_key
            or len(idempotency_key)>200 or idempotency_key.strip()!=idempotency_key):
            raise ModelJudgeRequestRejected('JUDGE_CALLER_INPUT_REQUIRED')
        scope=TenantScope(principal.org_id,principal.project_id)
        payload=self._derive_with_rule(conn,scope,principal.subject,body,release_policy=release_policy,artifact_bytes=artifact_bytes)
        return self._persist(conn,scope,idempotency_key,payload)

    def require_current_with_rule(self,conn,scope,request_id,request_hash,*,release_policy,artifact_bytes):
        import re
        self._caller(conn,scope)
        if (type(request_id) is not str or not request_id or request_id.strip()!=request_id
            or type(request_hash) is not str or re.fullmatch(r'[0-9a-f]{64}',request_hash) is None):
            raise ModelJudgeRequestRejected('JUDGE_CURRENT_REQUEST_INPUT_REQUIRED')
        with conn.cursor(row_factory=dict_row) as cur:
            row=cur.execute("""SELECT request_id,request_hash,request_json,created_by,expires_at
                FROM aip_model_eval_judge_request WHERE org_id=%s AND project_id=%s AND request_id=%s""",
                (*scope.key,request_id)).fetchone()
        if row is None or row['request_hash']!=request_hash or canonical_hash(row['request_json'])!=request_hash:
            raise ModelJudgeRequestRejected('JUDGE_CURRENT_REQUEST_HASH_REQUIRED')
        try:
            p=row['request_json']
            if p['schemaVersion']!='aos.model-judge-call-request/v2':
                raise ValueError('mandatory signed rule source request required')
            target=p['targetApplication'];judge=p['judgeGovernanceApplication']
            body=ModelJudgeCallRuleRequestInput(targetRequestId=target['requestId'],targetRequestHash=target['requestHash'],
                targetApprovalEventId=target['approvalEventId'],judgeRequestId=judge['requestId'],judgeRequestHash=judge['requestHash'],
                judgeApprovalEventId=judge['approvalEventId'],upperBoundMinor=p['upperBoundMinor'],expiresAt=p['expiresAt'],
                ruleSource=p['ruleFacts']['source'])
        except (KeyError,TypeError,ValueError) as exc:
            raise ModelJudgeRequestRejected('JUDGE_CURRENT_MANDATORY_RULE_REQUEST_INVALID') from exc
        derived=self._derive_with_rule(conn,scope,row['created_by'],body,release_policy=release_policy,artifact_bytes=artifact_bytes)
        if derived!=p or canonical_hash(derived)!=request_hash or body.expires_at!=row['expires_at']:
            raise ModelJudgeRequestRejected('JUDGE_CURRENT_RULE_REQUEST_REDERIVATION_DRIFTED')
        return dict(row)
