"""Fixed archived-source profile; missing archives skip, never qualify the strict runner.

Mocked Registry/loader and synthetic Stores are not live authority. Archive-free
checkouts do not silently substitute another bundle or regenerate signing keys.
"""
from pathlib import Path
from types import SimpleNamespace
import unittest
from tempfile import TemporaryDirectory
from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
import json
import hashlib
import sys
from types import ModuleType
from unittest.mock import patch

from aos_api.aip_solution_pack_publisher import AipSolutionPackPublisher, AipSolutionPackInvalid
from aos_api import aip_solution_pack_signed_preflight as preflight
from aos_api.asset_registry.contracts import BundleEvidenceStatus, BundleEvidenceType

ROOT = Path(__file__).resolve().parents[4]
PUBLIC = ROOT / '.evidence/qyh-full-system-restoration-20261011/selected-public-bundles'
VERSION = '1.13.0'
REF = 'bundle://m2-exact/solution.ecommerce.growth/1.13.0'
HASH = 'sha256:' + 'a' * 64
FP = 'sha256:' + 'b' * 64


class ExactDefinitionSourceTests(unittest.TestCase):
    @staticmethod
    def require_public_source():
        if (not (PUBLIC / 'solution.ecommerce.growth' / VERSION / 'bundle.yaml').is_file()
                or not (PUBLIC.parent / 'restoration-public-trust-roots.json').is_file()):
            raise unittest.SkipTest('fixed public signed archive absent; no source qualification')

    def real_source(self):
        self.require_public_source()
        from aos_api.asset_registry.manifest_loader import ManifestLoader
        from aos_api.asset_registry.signature import FileTrustRootProvider
        loader = ManifestLoader({'m2-exact': PUBLIC}, trust_roots=FileTrustRootProvider(
            PUBLIC.parent / 'restoration-public-trust-roots.json'))
        loaded = loader.load(REF)
        signature = next(x for x in loaded.evidence
                         if x.type == BundleEvidenceType.SIGNATURE_VERIFICATION)
        candidate = SimpleNamespace(publisher='aos', id='solution.ecommerce.growth',
            version=VERSION, content_hash=loaded.content_hash,
            signature_fingerprint=signature.artifact_hash)
        reader = SimpleNamespace(read=lambda: SimpleNamespace(candidates=[candidate],
            snapshot_hash='sha256:' + 'c' * 64))
        return reader, loader

    def test_actual_public_113_content_and_old_fixed_default(self):
        self.require_public_source()
        result = AipSolutionPackPublisher.inspect_exact_candidate(
            PUBLIC / 'solution.ecommerce.growth' / VERSION, expected_version=VERSION,
        )
        self.assertEqual((result.bundle_version, result.agent_count, result.skill_count,
                          result.capability_count), (VERSION, 6, 37, 10))
        with self.assertRaises(AipSolutionPackInvalid):
            AipSolutionPackPublisher.inspect_current_candidate(
                PUBLIC / 'solution.ecommerce.growth' / VERSION,
            )

    def test_explicit_content_version_rejects_aliases_paths_and_mismatch(self):
        self.require_public_source()
        path = PUBLIC / 'solution.ecommerce.growth' / VERSION
        for version in ('latest', '../1.13.0', '01.13.0', '1.13', '', True, '1.13.0 ', '1.12.0'):
            with self.subTest(version=version), self.assertRaises(AipSolutionPackInvalid):
                AipSolutionPackPublisher.inspect_exact_candidate(path, expected_version=version)

    def setup_source(self):
        self.require_public_source()
        candidate = SimpleNamespace(publisher='aos', id='solution.ecommerce.growth',
                                    version=VERSION, content_hash=HASH, signature_fingerprint=FP)
        snapshot = SimpleNamespace(candidates=[candidate], snapshot_hash='sha256:' + 'c' * 64)
        loaded = SimpleNamespace(source_ref=REF, content_hash=HASH,
            manifest=SimpleNamespace(metadata=SimpleNamespace(id=candidate.id,
                version=VERSION, publisher='aos')),
            evidence=[SimpleNamespace(type=BundleEvidenceType.SIGNATURE_VERIFICATION,
                status=BundleEvidenceStatus.VALID, artifact_hash=FP)])
        calls = []

        def load(ref):
            calls.append(ref)
            return loaded

        return candidate, snapshot, loaded, calls, SimpleNamespace(load=load)

    def invoke(self, snapshot, loader, **changes):
        options = dict(reader=SimpleNamespace(read=lambda: snapshot), loader=loader,
                       signed_root=PUBLIC, source_ref=REF)
        options.update(changes)
        return preflight.inspect_exact_signed_source(**options)

    def test_exact_source_113_uses_two_loads_and_distinct_proof(self):
        _, snapshot, _, calls, loader = self.setup_source()
        proof = self.invoke(snapshot, loader)
        self.assertIs(type(proof), preflight.ExactDefinitionSourceProof)
        self.assertNotIsInstance(proof, preflight.CurrentDefinitionSourceProof)
        self.assertEqual((proof.bundle_version, proof.source_ref), (VERSION, REF))
        self.assertEqual((proof.agent_count, proof.skill_count, proof.capability_count), (6, 37, 10))
        self.assertEqual(calls, [REF, REF])

    def test_source_ref_invalid_or_implicit_versions_rejected_before_reader(self):
        for ref in ('bundle://m2-exact/solution.ecommerce.growth/latest',
                    'bundle://m2-exact/solution.ecommerce.growth/01.13.0',
                    'bundle://m2-exact/solution.ecommerce.growth/../1.13.0',
                    'bundle://m2-exact/other/1.13.0', REF + '/', True, ''):
            with self.subTest(ref=ref), patch.object(SimpleNamespace(), 'read', create=True) as read:
                with self.assertRaises(preflight.CurrentDefinitionSourceBlocked):
                    preflight.inspect_exact_signed_source(reader=SimpleNamespace(read=read),
                        loader=object(), signed_root=PUBLIC, source_ref=ref)
                read.assert_not_called()

    def test_exact_source_rejects_current_snapshot_and_load_drift(self):
        for drift in ('missing', 'duplicate', 'hash', 'signature', 'signature-status',
                      'signature-missing', 'source', 'version', 'second-load'):
            candidate, snapshot, loaded, calls, loader = self.setup_source()
            if drift == 'missing': snapshot.candidates = []
            elif drift == 'duplicate': snapshot.candidates.append(candidate)
            elif drift == 'hash': candidate.content_hash = 'sha256:' + 'd' * 64
            elif drift == 'signature': loaded.evidence[0].artifact_hash = 'sha256:' + 'd' * 64
            elif drift == 'signature-status': loaded.evidence[0].status = BundleEvidenceStatus.INVALID
            elif drift == 'signature-missing': loaded.evidence = []
            elif drift == 'source': loaded.source_ref = REF.replace('m2-exact', 'other')
            elif drift == 'version': loaded.manifest.metadata.version = '1.11.0'
            else:
                original = loader.load
                def second_load(ref):
                    result = original(ref)
                    if len(calls) == 2: result.content_hash = 'sha256:' + 'd' * 64
                    return result
                loader.load = second_load
            with self.subTest(drift=drift), self.assertRaises(preflight.CurrentDefinitionSourceBlocked):
                self.invoke(snapshot, loader)
            self.assertLessEqual(len(calls), 2)

    def test_symlink_root_or_bundle_directory_rejected(self):
        _, snapshot, _, _, loader = self.setup_source()
        with TemporaryDirectory(prefix='aos-exact-source-unit-') as temp:
            root = Path(temp)
            link = root / 'root-link'
            link.symlink_to(PUBLIC, target_is_directory=True)
            with self.assertRaises(preflight.CurrentDefinitionSourceBlocked):
                self.invoke(snapshot, loader, signed_root=link)
            bundle = root / 'solution.ecommerce.growth' / VERSION
            bundle.parent.mkdir()
            bundle.symlink_to(PUBLIC / 'solution.ecommerce.growth' / VERSION,
                              target_is_directory=True)
            with self.assertRaises(preflight.CurrentDefinitionSourceBlocked):
                self.invoke(snapshot, loader, signed_root=root)
            with self.assertRaises(AipSolutionPackInvalid):
                AipSolutionPackPublisher.inspect_exact_candidate(bundle, expected_version=VERSION)

    def test_verified_ram_documents_build_all_requests_before_any_write(self):
        reader, loader = self.real_source()
        proof, documents = preflight.read_exact_definition_documents(
            reader=reader, loader=loader, signed_root=PUBLIC, source_ref=REF)
        with self.assertRaises(TypeError):
            documents['bundle.yaml'] = b'changed'
        batch = AipSolutionPackPublisher._prepare_requests(documents,
            expected_version=VERSION, source_revision=VERSION)
        self.assertEqual((len(batch.agents), len(batch.skills), len(batch.capabilities)), (6, 37, 10))
        self.assertEqual(proof.bundle_version, VERSION)
        self.assertTrue(all(x.source_ref.revision == VERSION
                            for x in (*batch.agents, *batch.skills, *batch.capabilities)))
        self.assertTrue(all(x.lifecycle.value == 'evaluated' for x in batch.skills))

    def test_all_53_constructor_payloads_match_pre_refactor_source(self):
        # Frozen previously reviewed repository code, only fake Stores, no real writer.
        path = ROOT / '.evidence/qyh-m2-exact-definition-source-20261023/frozen-publisher-r1.txt'
        self.require_public_source()
        if not path.is_file():
            self.skipTest('fixed consumed constructor baseline absent; no equivalence qualification')
        name = 'exact_source_constructor_baseline'
        module = ModuleType(name)
        sys.modules[name] = module
        before, after = [], []
        class Store:
            def __init__(self, target):
                self.target = target
            def save(self, request, *, actor):
                self.target.append(request.model_dump(mode='json', by_alias=True))
                return request
            publish = publish_template = publish_skill = save
        try:
            raw = path.read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),
                'f97ffb7acce9640e79835b06749018ba196c34aa84f662d262d5016f1e381d5e')
            exec(compile(raw, str(path), 'exec'), module.__dict__)
            old = module.AipSolutionPackPublisher(agent_store=Store(before),
                skill_store=Store(before), capability_store=Store(before))
            old._publish(PUBLIC / 'solution.ecommerce.growth' / VERSION,
                actor='synthetic-constructor-equivalence', expected_version=VERSION,
                source_revision=VERSION)
            reader, loader = self.real_source()
            _, documents = preflight.read_exact_definition_documents(reader=reader, loader=loader,
                signed_root=PUBLIC, source_ref=REF)
            new = AipSolutionPackPublisher(agent_store=Store(after),
                skill_store=Store(after), capability_store=Store(after))
            new._write_requests(new._prepare_requests(documents, expected_version=VERSION,
                source_revision=VERSION), actor='synthetic-constructor-equivalence')
        finally:
            del sys.modules[name]
        self.assertEqual(len(before), 53)
        self.assertEqual(after, before)

    def test_verified_ram_rejects_changed_artifact_and_late_source(self):
        for drift in ('bytes', 'late-source'):
            reader, loader = self.real_source()
            with self.subTest(drift=drift):
                if drift == 'bytes':
                    with patch.object(loader, 'read_verified_artifact', return_value=b'{}'):
                        with self.assertRaises(preflight.CurrentDefinitionSourceBlocked):
                            preflight.read_exact_definition_documents(
                                reader=reader, loader=loader, signed_root=PUBLIC, source_ref=REF)
                else:
                    original = reader.read
                    calls = []
                    def read():
                        value = original()
                        calls.append(1)
                        if len(calls) > 1:
                            value.candidates = []
                        return value
                    reader.read = read
                    with self.assertRaises(preflight.CurrentDefinitionSourceBlocked):
                        preflight.read_exact_definition_documents(
                            reader=reader, loader=loader, signed_root=PUBLIC, source_ref=REF)

    def publication_fixture(self, *, fail=False, prior_intent=False):
        from aos_api import aip_solution_pack_publisher as publication
        from aos_api.aip_agent_registry_store import AipAgentRegistryStore
        from aos_api.auth import Principal
        from aos_api.aip_network_issuer_attempt import AttemptAlreadyRecorded
        from psycopg.pq import TransactionStatus
        reader, loader = self.real_source()
        class Connection:
            info = SimpleNamespace(transaction_status=TransactionStatus.IDLE)
            autocommit = False
            read_only = False
            receipt = None
            commits = 0
            rollbacks = 0
            writes = 0
            records = {}
            role = 'owner'
            registry_available = True
            registry_hash = reader.read().candidates[0].content_hash
            registry_status = 'published'
            after_write = None
            @contextmanager
            def transaction(self):
                old_records = dict(self.records)
                old_receipt = self.receipt
                self.info = SimpleNamespace(transaction_status=TransactionStatus.INTRANS)
                try:
                    yield self
                    self.commits += 1
                except Exception:
                    self.records = old_records
                    self.receipt = old_receipt
                    self.rollbacks += 1
                    raise
                finally:
                    self.info = SimpleNamespace(transaction_status=TransactionStatus.IDLE)
            def execute(self, query, params=()):
                if 'FROM meta_membership' in query:
                    return SimpleNamespace(fetchall=lambda: [{'role': self.role}])
                if 'FROM asset_bundle_version' in query:
                    return SimpleNamespace(fetchall=lambda: (
                        [{'version_pk': 'synthetic-version', 'content_hash': self.registry_hash,
                          'status': self.registry_status}] if self.registry_available else []))
                if 'SELECT * FROM aip_agent_registry_receipt' in query:
                    return SimpleNamespace(fetchone=lambda: self.receipt)
                if 'INSERT INTO aip_agent_registry_receipt' in query:
                    self.receipt = dict(zip(
                        ['org_id','project_id','receipt_id','operation','idempotency_key',
                         'request_hash','resource_ref','result_ref','created_by','created_at'], params))
                    self.receipt['status'] = 'applied'
                    for key in ('resource_ref', 'result_ref'):
                        self.receipt[key] = json.loads(self.receipt[key])
                    return SimpleNamespace(fetchone=lambda: self.receipt)
                if query == 'fixture-write':
                    kind, item = params
                    self.writes += 1
                    if fail and self.writes == 2:
                        raise RuntimeError('synthetic Store unknown')
                    identifier = getattr(item, {'agent':'template_id', 'skill':'skill_id',
                                                'capability':'capability_id'}[kind])
                    self.records[(kind, identifier, item.revision)] = item
                    if self.after_write:
                        self.after_write()
                return SimpleNamespace(fetchone=lambda: None)
        conn = Connection()
        conn.reader = reader
        @contextmanager
        def factory(scope):
            if scope.key != ('org-org', 'dev-project'):
                raise PermissionError('test factory scope')
            yield conn
        class Agent(AipAgentRegistryStore):
            def put(self, kind, request):
                with self._connect_factory() as bound:
                    bound.execute('fixture-write', (kind, request))
                    bound.commit()
                return request
            def publish_template(self, request, *, actor):
                return self.put('agent', request)
            def get_template(self, identifier, revision):
                return conn.records[('agent', identifier, revision)]
        class Skill(Agent):
            def publish_skill(self, request, *, actor):
                return self.put('skill', request)
            def get_skill(self, identifier, revision):
                return conn.records[('skill', identifier, revision)]
        class Capability(Agent):
            def publish(self, request, *, actor):
                return self.put('capability', request)
            def get(self, identifier, revision):
                return conn.records[('capability', identifier, revision)]
        publisher = AipSolutionPackPublisher(agent_store=object(), skill_store=object(),
                                             capability_store=object())
        marker_calls = []
        def marker(*args, **kwargs):
            marker_calls.append(1)
            if prior_intent:
                raise AttemptAlreadyRecorded('synthetic prior intent')
        @contextmanager
        def invoke():
            with ExitStack() as stack:
                for name, value in [('AipAgentRegistryStore', Agent), ('AipSkillRegistry', Skill),
                                    ('AipCapabilityRegistry', Capability)]:
                    stack.enter_context(patch.object(publication, name, value))
                import aos_api.aip_network_issuer_attempt as attempts
                stack.enter_context(patch.object(attempts, '_reserve_attempt_receipt', side_effect=marker))
                options = dict(
                    principal=Principal(subject='synthetic-definition-author', org_id='org-org',
                        project_id='dev-project', token_kind='oidc', roles=['asset-publisher'],
                        asset_publishers=frozenset({'aos'})),
                    connect_factory=factory, reader=reader, loader=loader,
                    signed_root=PUBLIC, source_ref=REF, idempotency_key='synthetic-exact-source',
                    attempt_directory=Path('/nonexistent-source-unit-intent'))
                yield lambda **changes: publisher.publish_exact_verified(**{**options, **changes})
        return conn, marker_calls, invoke

    def test_exact_publication_single_outer_transaction_and_native_receipt_replay(self):
        conn, marker, invoke = self.publication_fixture()
        with invoke() as run:
            result, receipt = run()
            self.assertEqual((result.agent_count, result.skill_count, result.capability_count), (6, 37, 10))
            self.assertEqual(conn.writes, 53)
            self.assertEqual(conn.commits, 1)
            replay, replay_receipt = run()
        self.assertEqual(replay, result)
        self.assertEqual(replay_receipt, receipt)
        self.assertEqual(conn.writes, 53)
        self.assertEqual(len(marker), 1)
        self.assertEqual(conn.rollbacks, 0)

    def test_unknown_intent_or_store_failure_never_commits_or_resends(self):
        for fail, prior in ((False, True), (True, False)):
            conn, marker, invoke = self.publication_fixture(fail=fail, prior_intent=prior)
            with self.subTest(fail=fail, prior=prior), invoke() as run:
                with self.assertRaises(RuntimeError):
                    run()
            self.assertEqual(conn.commits, 0)
            self.assertEqual(conn.rollbacks, 1)
            self.assertIsNone(conn.receipt)
            self.assertFalse(conn.records)
            self.assertEqual(len(marker), 1)
            self.assertEqual(conn.writes, 2 if fail else 0)

    def test_current_member_registry_and_native_receipt_drift_remain_closed(self):
        from aos_api.asset_registry.errors import DutySeparationRequiredError
        from aos_api.auth import Principal
        for failure in ('identity', 'publisher', 'key', 'readonly', 'autocommit',
                        'member', 'registry', 'registry-hash', 'registry-status',
                        'receipt', 'immutable-row'):
            conn, marker, invoke = self.publication_fixture()
            with self.subTest(failure=failure), invoke() as run:
                if failure in ('identity', 'publisher', 'key'):
                    pass
                elif failure == 'readonly':
                    conn.read_only = True
                elif failure == 'autocommit':
                    conn.autocommit = True
                elif failure == 'member':
                    conn.role = 'viewer'
                elif failure == 'registry':
                    conn.registry_available = False
                elif failure == 'registry-hash':
                    conn.registry_hash = 'sha256:' + '0' * 64
                elif failure == 'registry-status':
                    conn.registry_status = 'revoked'
                else:
                    run()
                    if failure == 'receipt':
                        conn.receipt['result_ref']['resourceId'] = 'synthetic-wrong-batch'
                    else:
                        key = next(iter(conn.records))
                        conn.records[key] = conn.records[key].model_copy(
                            update={'content_hash': '0' * 64})
                prior_writes = conn.writes
                with self.assertRaises((ValueError, DutySeparationRequiredError)):
                    changes = ({'principal': object()} if failure == 'identity'
                               else {'principal': Principal(subject='synthetic-definition-author',
                                   org_id='org-org', project_id='dev-project', token_kind='oidc',
                                   roles=['asset-publisher'])} if failure == 'publisher'
                               else {'idempotency_key': '   '} if failure == 'key' else {})
                    run(**changes)
                self.assertEqual(conn.writes, prior_writes)
                self.assertEqual(len(marker), 1 if failure in ('receipt', 'immutable-row') else 0)

    def test_source_revocation_before_outer_commit_rolls_back_full_fake_batch(self):
        conn, marker, invoke = self.publication_fixture()
        conn.after_write = lambda: setattr(conn.reader, 'read', lambda: SimpleNamespace(
            candidates=[], snapshot_hash='sha256:' + 'c' * 64))
        with invoke() as run, self.assertRaises(preflight.CurrentDefinitionSourceBlocked):
            run()
        self.assertEqual(conn.writes, 53)
        self.assertEqual(conn.commits, 0)
        self.assertEqual(conn.rollbacks, 1)
        self.assertFalse(conn.records)
        self.assertIsNone(conn.receipt)
        self.assertEqual(len(marker), 1)


class ExactSourceInstallerTests(unittest.TestCase):
    def fixture(self, *, exact=True):
        from aos_api.aip_ecommerce_agent_installer import AipEcommerceAgentInstaller
        from aos_api.aip_agent_registry_contracts import (
            AgentTemplateRevision, SkillTemplateRevision, CapabilityRevision,
            AgentInstance, VersionedAssetRef, RegistryReceipt,
        )
        from aos_api.aip_agent_registry_store import AipAgentRegistryNotFound
        from aos_api.aip_contracts import ResourceRef, TenantContext
        from aos_api.auth import Principal
        now = datetime(2026, 10, 23, tzinfo=timezone.utc)
        reader, loader = ExactDefinitionSourceTests().real_source()
        _, docs = preflight.read_exact_definition_documents(reader=reader, loader=loader,
            signed_root=PUBLIC, source_ref=REF)
        batch = AipSolutionPackPublisher._prepare_requests(docs,
            expected_version=VERSION, source_revision=VERSION)
        groups = [
            [owner(**req.model_dump(), created_by='synthetic-definition-author', created_at=now)
             for req in requests]
            for owner, requests in [(AgentTemplateRevision, batch.agents),
                                    (SkillTemplateRevision, batch.skills),
                                    (CapabilityRevision, batch.capabilities)]
        ]
        calls = []
        class Registry:
            def __init__(self, kind, rows):
                self.kind = kind
                self.rows = {VERSION: list(rows)}
                self.instances = {}
                self.created = []
            def _list(self, **kwargs):
                calls.append((self.kind, kwargs['source_revision']))
                return self.rows.get(kwargs['source_revision'], [])
            list_templates = list_skills = list_capabilities = _list
            def get_instance(self, scope, identifier):
                key = (scope.key, identifier)
                if key not in self.instances:
                    raise AipAgentRegistryNotFound('synthetic instance absent')
                return self.instances[key]
            def create_instance(self, scope, request, *, idempotency_key, actor, occurred_at):
                self.created.append((scope, request, idempotency_key, actor))
                tenant = TenantContext(org_id=scope.org_id, project_id=scope.project_id)
                instance = AgentInstance(tenant=tenant, instance_id=request.instance_id,
                    instance_ref=VersionedAssetRef(asset_type='AgentInstance',
                        asset_id=request.instance_id, revision=1, content_hash='0' * 64),
                    template=request.template, status=request.initial_status,
                    overlay=request.overlay, version=1, created_by=actor,
                    created_at=occurred_at, updated_at=occurred_at)
                receipt = RegistryReceipt(tenant=tenant,
                    receipt_id='synthetic-agent-' + str(len(self.created)),
                    operation='agent_instance.create', idempotency_key=idempotency_key,
                    request_hash='0' * 64, resource_ref=ResourceRef(resource_type='AgentTemplate',
                        resource_id=request.template.asset_id, revision=str(request.template.revision),
                        authority='postgresql'), result_ref=ResourceRef(
                            resource_type='AgentInstance', resource_id=request.instance_id,
                            revision='1', authority='postgresql'),
                    status='applied', created_by=actor, created_at=occurred_at)
                self.instances[(scope.key, request.instance_id)] = instance
                return instance, receipt
        stores = [Registry(name, rows) for name, rows in zip(('agents', 'skills', 'capabilities'), groups)]
        kwargs = dict(agents=stores[0], skills=stores[1], capabilities=stores[2],
            capability_bindings=object(), clock=lambda: now)
        if exact:
            kwargs['source_revision'] = VERSION
        installer = AipEcommerceAgentInstaller(**kwargs)
        principal = Principal(subject='synthetic-exact-installer', org_id='org-org',
                              project_id='dev-project', token_kind='oidc')
        return installer, stores, groups, calls, principal

    def test_explicit_installer_reads_only_selected_version(self):
        installer, stores, groups, calls, principal = self.fixture()
        selected = installer._definitions(principal)
        self.assertEqual(tuple(map(len, selected)), (6, 37, 10))
        self.assertEqual(calls, [(name, VERSION) for name in ('agents', 'skills', 'capabilities')])
        self.assertIs(selected[0][groups[0][0].template_id], groups[0][0])
        self.assertTrue(all(not store.created for store in stores))

    def test_explicit_missing_or_partial_source_never_falls_back(self):
        from aos_api.aip_ecommerce_agent_installer import AipEcommerceCatalogInvalid
        for missing in ('all', 0, 1, 2):
            installer, stores, groups, calls, principal = self.fixture()
            for index, store in enumerate(stores):
                store.rows['1.11.0'] = list(groups[index])
                store.rows['1.2.0'] = list(groups[index])
                if missing == 'all':
                    store.rows[VERSION] = []
                elif missing == index:
                    store.rows[VERSION] = store.rows[VERSION][:-1]
            with self.subTest(missing=missing), self.assertRaises(AipEcommerceCatalogInvalid):
                installer.install(principal, idempotency_key='synthetic-no-fallback')
            self.assertEqual({revision for _, revision in calls}, {VERSION})
            self.assertTrue(all(not store.created for store in stores))

    def test_explicit_source_ref_duplicate_or_unknown_rows_rejected(self):
        from aos_api.aip_ecommerce_agent_installer import AipEcommerceCatalogInvalid
        from aos_api.aip_contracts import ResourceRef
        for failure in ('version', 'kind', 'authority', 'id', 'duplicate'):
            installer, stores, groups, calls, principal = self.fixture()
            row = groups[0][0]
            if failure == 'duplicate':
                stores[0].rows[VERSION].append(row)
            elif failure == 'id':
                stores[0].rows[VERSION][0] = row.model_copy(update={'template_id': 'unrelated-role'})
            else:
                ref = row.source_ref.model_dump()
                ref[{'version':'revision', 'kind':'resource_type', 'authority':'authority'}[failure]] = {
                    'version':'1.11.0', 'kind':'Other', 'authority':'other-authority'}[failure]
                stores[0].rows[VERSION][0] = row.model_copy(
                    update={'source_ref': ResourceRef.model_validate(ref)})
            with self.subTest(failure=failure), self.assertRaises(AipEcommerceCatalogInvalid):
                installer.install(principal, idempotency_key='synthetic-closed-source')
            self.assertTrue(all(not store.created for store in stores))

    def test_same_source_revisions_select_latest_without_foreign_publication(self):
        from aos_api.aip_contracts import TenantContext
        from aos_api.aip_ecommerce_agent_installer import AipEcommerceCatalogInvalid
        installer, stores, groups, calls, principal = self.fixture()
        original = groups[1][0]
        newer = original.model_copy(update={'revision': 2})
        foreign = original.model_copy(update={'revision': 3,
            'publication_tenant': TenantContext(org_id='dev-org', project_id='dev-project')})
        stores[1].rows[VERSION].extend((newer, foreign))
        selected = installer._definitions(principal)
        self.assertIs(selected[1][original.skill_id], newer)
        stores[1].rows[VERSION] = [item.model_copy(update={'publication_tenant':
            TenantContext(org_id='dev-org', project_id='dev-project')}) for item in groups[1]]
        with self.assertRaises(AipEcommerceCatalogInvalid):
            installer._definitions(principal)
        self.assertTrue(all(not store.created for store in stores))

    def test_exact_install_uses_original_dto_provisioning_and_existing_conflict(self):
        from aos_api.aip_ecommerce_agent_installer import AipEcommerceCatalogInvalid
        from aos_api.aip_agent_registry_contracts import AgentInstanceStatus
        installer, stores, _, calls, principal = self.fixture()
        result = installer.install(principal, idempotency_key='synthetic-install')
        self.assertEqual((result.solution_pack_version, result.created_count), (VERSION, 6))
        self.assertTrue(all(x.instance.status is AgentInstanceStatus.PROVISIONING for x in result.items))
        self.assertEqual(len(stores[0].created), 6)
        replay = installer.install(principal, idempotency_key='synthetic-install')
        self.assertEqual((replay.created_count, replay.existing_count), (0, 6))
        self.assertEqual(len(stores[0].created), 6)
        key = next(iter(stores[0].instances))
        existing = stores[0].instances[key]
        stores[0].instances[key] = existing.model_copy(update={
            'template': existing.template.model_copy(update={'content_hash': 'f' * 64})})
        with self.assertRaises(AipEcommerceCatalogInvalid):
            installer.install(principal, idempotency_key='synthetic-drift')
        self.assertEqual(len(stores[0].created), 6)

    def test_invalid_explicit_revision_and_static_default_compatibility(self):
        from aos_api.aip_ecommerce_agent_installer import AipEcommerceAgentInstaller, AipEcommerceCatalogInvalid
        for value in ('latest', '01.13.0', '../1.13.0', True, ''):
            with self.subTest(value=value), self.assertRaises(ValueError):
                AipEcommerceAgentInstaller(source_revision=value)
        installer, _, _, _, principal = self.fixture()
        templates = installer._definitions(principal)[0]
        self.assertEqual(AipEcommerceAgentInstaller._solution_version(
            templates, source_revision=VERSION), VERSION)
        with self.assertRaises(AipEcommerceCatalogInvalid):
            AipEcommerceAgentInstaller._solution_version(templates, source_revision='1.12.0')


if __name__ == '__main__':
    unittest.main()
