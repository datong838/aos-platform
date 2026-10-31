"""Exact four public releases for a future isolated three-backend lifecycle case.

Import has no effects. Database functions require the future runner's explicit
guarded factory; never use a default production connection. Fixture actors below
are synthetic test identities, not human/OIDC approvals or business authority.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from types import MappingProxyType, SimpleNamespace

from aos_api.asset_registry.composition_contracts import (
    ApproveInstallationRequest, CompositionRequest, CreateInstallationRequest,
    EmptyInstallationActionRequest,
)
from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.asset_registry.contracts import BundleVersionStatus, LoadedBundle
from aos_api.asset_registry.installation_revalidation import InstallationRevalidator
from aos_api.asset_registry.installation_service import InstallationService
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.registry_service import RegistryService
from aos_api.asset_registry.registry_snapshot import RegistrySnapshotReader
from aos_api.asset_registry.registry_store import PostgresRegistryStore
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.asset_registry.resolver import resolve
from aos_api.asset_registry.signature import FileTrustRootProvider
from aos_api.extension_runtime.lifecycle_service import RuntimeLifecycleService
from aos_api.extension_runtime.release_revalidation import RuntimeReleaseRevalidator
from aos_api.extension_runtime.runtime_uninstall import RuntimeUninstallGuard

ROOT = Path(__file__).absolute().parents[4]
PUBLIC = ROOT / '.evidence/qyh-full-system-restoration-20261011'
TRUST = PUBLIC / 'restoration-public-trust-roots.json'
TRUST_SHA = '7c8a294f5273efd7df493b07c792f6a265b9f2f5ab03a6719b10e95ad2a19a1d'
EXPECTED = MappingProxyType({
    'domain.ecommerce.core': ('1.4.3', 'sha256:e14e6af72dd7c89d5beb7fd002454029bbc64cf510e6b9849ae9df20ef7eba44'),
    'platform.ecommerce.niushop': ('1.23.2', 'sha256:052214c06f08bd930daea552f7ade0ee49313abde9e3292fdaa8d071d41a8c90'),
    'solution.ecommerce.growth': ('1.13.0', 'sha256:24249a21939b3a6c68c493b5f3bc958cbd0a1ba28b4c8f57a2f2da6b68308669'),
    'solution.ecommerce.operations-base': ('1.2.2', 'sha256:ca0f6e74bcb428efd78c868285cd9fbed136919d4676b46aee9e181e8eec33ec'),
})
BACKEND_IDS = frozenset(set(EXPECTED) - {'solution.ecommerce.operations-base'})
ALIAS = 'qyh-m2-selected'


def _pinned_trust_bytes():
    directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in TRUST.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(TRUST.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        try:
            before = os.fstat(fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or before.st_nlink != 1
                    or before.st_mode & stat.S_IWOTH or before.st_size > 65536):
                raise ValueError('fixed public trust metadata rejected')
            raw = os.read(fd, 65537)
            after = os.fstat(fd)
            fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
            if (any(getattr(before, k) != getattr(after, k) for k in fields)
                    or len(raw) != before.st_size or hashlib.sha256(raw).hexdigest() != TRUST_SHA):
                raise ValueError('fixed public trust changed')
            return raw
        finally:
            os.close(fd)
    finally:
        os.close(directory)


@dataclass(frozen=True)
class SelectedPackages:
    loaded: tuple
    trust_roots: object

    def __post_init__(self):
        if type(self.loaded) is not tuple or len(self.loaded) != 4:
            raise ValueError('exact four selected public members required')
        if not callable(getattr(self.trust_roots, 'get_trust_root', None)):
            raise ValueError('public trust snapshot required')
        found = {}
        for item in self.loaded:
            if type(item) is not LoadedBundle:
                raise ValueError('original loaded bundle model required')
            metadata = item.manifest.metadata
            if (metadata.publisher != 'aos' or metadata.id in found
                    or EXPECTED.get(metadata.id) != (metadata.version, item.content_hash)
                    or item.source_ref != f'bundle://{ALIAS}/{metadata.id}/{metadata.version}'):
                raise ValueError('selected public member identity changed')
            found[metadata.id] = item
            record = SimpleNamespace(publisher=metadata.publisher, manifest=item.manifest,
                content_hash=item.content_hash, signature=item.signature, status=BundleVersionStatus.DRAFT,
                evidence=item.evidence, persisted_manifest=None,
                artifacts=[{'relativePath': a.relative_path, 'digest': a.digest, 'size': a.size,
                            'mediaType': a.media_type} for a in item.artifacts])
            ReleasePolicy(trust_roots=self.trust_roots).evaluate(
                record, checked_at=datetime.now(timezone.utc), require_published=False)
        if set(found) != set(EXPECTED) or set(self.backend_ids) != BACKEND_IDS:
            raise ValueError('selected three-backend group changed')

    @property
    def backend_ids(self):
        return tuple(x.manifest.metadata.id for x in self.loaded
                     if x.manifest.spec.runtime is not None and x.manifest.spec.runtime.backend is not None)


def load_selected_packages():
    _pinned_trust_bytes()
    trust = FileTrustRootProvider(TRUST).snapshot()
    public_root = PUBLIC / 'selected-public-bundles'
    if public_root.resolve(strict=True) != public_root:
        raise ValueError('fixed public root must not alias another path')
    loader = ManifestLoader({ALIAS: public_root}, trust_roots=trust)
    loaded = tuple(loader.load(f'bundle://{ALIAS}/{bid}/{version}')
                   for bid, (version, _digest) in EXPECTED.items())
    packages = SelectedPackages(loaded, trust)
    _pinned_trust_bytes()
    return packages


class FixedSelectedLoader:
    def __init__(self, packages):
        if type(packages) is not SelectedPackages:
            raise ValueError('selected fixture package set required')
        packages.__post_init__()
        self._packages = packages

    @property
    def trust_roots(self):return self._packages.trust_roots

    def load(self, source_ref):
        matches = [x for x in self._packages.loaded if x.source_ref == source_ref]
        if len(matches) != 1:
            raise ValueError('only exact selected public reference is allowed')
        return matches[0]


@dataclass(frozen=True)
class SelectedRegistry:
    connect: object
    packages: SelectedPackages
    registry: object


@dataclass(frozen=True)
class SelectedLabIdentity:
    database_name: str
    database_oid: int
    cluster_name: str
    administrator_role: str

    def __post_init__(self):
        identifiers = (self.database_name, self.administrator_role)
        if (any(type(item) is not str or re.fullmatch(r'[a-z][a-z0-9_]{0,62}', item) is None
                for item in identifiers)
                or type(self.database_oid) is not int or self.database_oid <= 0
                or type(self.cluster_name) is not str
                or re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}', self.cluster_name) is None):
            raise ValueError('explicit selected lab identity required')


def verify_selected_lab_identity(conn, binding, *, maintenance):
    """Read and match one injected isolated-lab identity; never grants access."""
    if type(binding) is not SelectedLabIdentity or type(maintenance) is not bool:
        raise ValueError('explicit selected lab identity required')
    row = conn.execute('''SELECT current_database() AS database_name,d.oid::bigint AS database_oid,
        current_setting('cluster_name') AS cluster_name,pg_get_userbyid(d.datdba) AS database_owner,
        current_user AS current_role,session_user AS session_role,
        administrator.rolsuper AS administrator_superuser,
        current_setting('server_version_num')::int AS server_version,clock_timestamp() AS now
        FROM pg_catalog.pg_database d JOIN pg_catalog.pg_roles administrator ON administrator.rolname=%s
        WHERE d.datname=current_database()''', (binding.administrator_role,)).fetchone()
    if (row is None or row['database_name'] != binding.database_name
            or row['database_oid'] != binding.database_oid
            or row['cluster_name'] != binding.cluster_name
            or row['database_owner'] != binding.administrator_role
            or row['administrator_superuser'] is not True
            or type(row['server_version']) is not int or not 160000 <= row['server_version'] < 170000):
        raise PermissionError('selected lab identity differs')
    if (maintenance and (row['current_role'] != binding.administrator_role
                         or row['session_role'] != binding.administrator_role)):
        raise PermissionError('selected lab identity differs')
    return dict(row)


def register_selected_registry(*, connect, packages):
    """Mutating fixture setup: future isolated runner only; never called on import."""
    if not callable(connect) or type(packages) is not SelectedPackages:
        raise ValueError('explicit isolated connector and selected packages required')
    loader = FixedSelectedLoader(packages)
    service = RegistryService(store=PostgresRegistryStore(connect), loader=loader, trust_roots=packages.trust_roots)
    for loaded in packages.loaded:
        metadata = loaded.manifest.metadata
        common = dict(publisher='aos', bundle_id=metadata.id, publisher_scopes={'aos'})
        service.create_bundle(**common, kind=loaded.manifest.kind, display_name=metadata.display_name,
            actor='synthetic-m2-three-release-author', roles={'developer'})
        service.create_version(**common, source_ref=loaded.source_ref,
            actor='synthetic-m2-three-release-author', roles={'developer'})
        service.validate(**common, version=metadata.version,
            actor='synthetic-m2-three-release-validator', roles={'developer'})
        service.publish(**common, version=metadata.version,
            actor='synthetic-m2-three-release-publisher', roles={'asset-publisher'})
    return SelectedRegistry(connect, packages, service)


def resolve_selected_case(registry, *, case_id, command_connect=None):
    """Create one new approved fixture installation via original services, not SQL seeds."""
    if type(case_id) is not str or re.fullmatch('m2-three-[a-z0-9][a-z0-9-]{0,38}', case_id) is None:
        raise ValueError('explicit synthetic three-backend case identity required')
    if type(registry) is not SelectedRegistry or not callable(registry.connect):
        raise ValueError('selected isolated registry fixture required')
    if command_connect is not None and not callable(command_connect):
        raise ValueError('explicit isolated uninstall command connector required')
    packages = registry.packages
    packages.__post_init__()
    connect = registry.connect
    policy = ReleasePolicy(trust_roots=packages.trust_roots)
    snapshot = RegistrySnapshotReader(connect_factory=connect, release_policy=policy).read()
    request = CompositionRequest.model_validate(dict(
        requested=[dict(publisher='aos', id=bid, version=v) for bid, (v, _h) in EXPECTED.items()],
        platformApiVersion='1.7.0', platformRelease='aos-platform/1.7.0', environment='dev',
        registrySnapshotHash=snapshot.snapshot_hash, currentInstallationRef=None))
    payload = resolve(request, snapshot, None)
    members = {(x.publisher, x.id, x.version, x.content_hash) for x in payload.resolved}
    if len(payload.resolved) != 4 or members != {('aos', bid, v, h) for bid, (v, h) in EXPECTED.items()}:
        raise ValueError('resolver did not select exact four-member lock')
    scope = dict(org_id='org-org', project_id='dev-project')
    author = 'synthetic-' + case_id + '-author'
    checker = 'synthetic-' + case_id + '-checker'
    compositions = PostgresCompositionStore(connect)
    lock = compositions.create_or_get(**scope, request=request, snapshot=snapshot, payload=payload, created_by=author)
    store = PostgresInstallationStore(connect)
    revalidator = RuntimeReleaseRevalidator(release_policy=policy)
    command_options = ({'uninstall_command_store': PostgresInstallationStore(command_connect)}
                       if command_connect is not None else {})
    service = InstallationService(store=store, composition_store=compositions,
        revalidator=InstallationRevalidator(release_policy=policy), planning_revalidator=revalidator,
        runtime_uninstall_guard=RuntimeUninstallGuard(), **command_options)
    draft_receipt = service.create(**scope, actor=author, roles=['asset-installer'], markings=[],
        idempotency_key=case_id+'-create', request=CreateInstallationRequest(
            compositionId=lock.composition_id, lockRevision=lock.revision,
            overlayRevision='isolated-three-backend', displayName='三后台隔离测试'))
    identity = draft_receipt.response_json['installationId']
    action = dict(**scope, installation_id=identity, actor=author, roles=['asset-installer'], markings=[])
    current = store.get_installation(**scope, installation_id=identity)
    service.submit(**action, request=EmptyInstallationActionRequest(), idempotency_key=case_id+'-submit',
                   if_match=f'"{current.etag_version}"')
    submitted = store.get_installation(**scope, installation_id=identity)
    service.approve(**{**action, 'actor':checker, 'roles':['asset-install-approver']},
        request=ApproveInstallationRequest(lockHash=lock.lock_hash, permissionDiffHash=lock.permission_diff_hash,
            migrationPlanHash=lock.migration_plan_hash, contributionDiffHash=lock.contribution_diff_hash),
        idempotency_key=case_id+'-approve', if_match=f'"{submitted.etag_version}"')
    approved = store.get_installation(**scope, installation_id=identity)
    if getattr(approved.state, 'value', approved.state) != 'approved':
        raise ValueError('fixture installation approval did not persist')
    lifecycle = RuntimeLifecycleService(installation_store=store, installation_reader=service, revalidator=revalidator)
    return SimpleNamespace(case_id=case_id, packages=packages, scope=scope, registry=registry, lock=lock,
        store=store, installation_service=service, revalidator=revalidator, lifecycle=lifecycle,
        action=action, approved=approved, composition_store=compositions)


def build_selected_preparation(*, registry, installation_store, revalidator,
                               driver, live_directory, platform, preparation_only):
    """Construct the original production graph; never starts or admits a job.

    Only the future isolated runner may drive the returned scheduler. Current
    membership, schema, configuration, and runtime admission remain production
    checks, not grants supplied by this fixture.
    """
    from aos_api.aip_runtime_configuration_sources import build_current_configuration_authorization
    from aos_api.asset_registry.control_policy import (
        APPLY_INSTALLATION_OPERATION, ENABLE_RUNTIME_OPERATION, VERIFY_INSTALLATION_OPERATION,
    )
    from aos_api.extension_runtime.configuration_authorization import CurrentConfigurationPermission
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.extension_runtime.live_job_directory import LivePreparedJobDirectory
    from aos_api.extension_runtime.oci_driver import OciDriver
    from aos_api.extension_runtime.production_preparation import ProductionPreparationDependencies
    from aos_api.tenant_scope import TenantScope

    if (type(registry) is not SelectedRegistry or not callable(registry.connect)
            or type(registry.packages) is not SelectedPackages
            or type(installation_store) is not PostgresInstallationStore
            or installation_store._connect_factory is not registry.connect
            or type(revalidator) is not RuntimeReleaseRevalidator
            or type(driver) is not OciDriver or driver.context != 'colima-aos-extension'
            or type(live_directory) is not LivePreparedJobDirectory
            or platform != 'linux/arm64' or type(preparation_only) is not bool):
        raise ValueError('exact selected isolated preparation graph required')
    packages = registry.packages
    packages.__post_init__()
    policy = revalidator._release_policy
    if type(policy) is not ReleasePolicy or policy._trust_roots is not packages.trust_roots:
        raise ValueError('selected preparation trust graph differs')
    _pinned_trust_bytes()
    loader = ManifestLoader({ALIAS: PUBLIC / 'selected-public-bundles'}, trust_roots=packages.trust_roots)
    authorization = build_current_configuration_authorization(
        permission=CurrentConfigurationPermission(installation_store=installation_store))
    dependencies = ProductionPreparationDependencies(
        connect=registry.connect, installation_store=installation_store, revalidator=revalidator,
        policy=policy, loader=loader,
        apply_permission=CurrentControlPermission(operation=APPLY_INSTALLATION_OPERATION),
        verification_permission=CurrentControlPermission(operation=VERIFY_INSTALLATION_OPERATION),
        enable_permission=CurrentControlPermission(operation=ENABLE_RUNTIME_OPERATION),
        configuration_authorize=authorization, driver=driver, platform=platform,
        live_directory=live_directory)
    scheduler = dependencies.build_scheduler(TenantScope('org-org', 'dev-project'),
                                             preparation_only=preparation_only)
    return SimpleNamespace(dependencies=dependencies, scheduler=scheduler)


def build_selected_runtime_control(*, registry, installation_reader, preparation):
    """Compose original configure/disable consumers without running or authorizing them."""
    from aos_api.asset_registry.control_policy import DISABLE_RUNTIME_OPERATION
    from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent
    from aos_api.extension_runtime.configuration_consumer import ConfigurationConsumer
    from aos_api.extension_runtime.configuration_stage_consumer import ConfigurationStageConsumer
    from aos_api.extension_runtime.configuration_service import RuntimeConfigurationService
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.extension_runtime.disable_consumer import RuntimeDisableConsumer
    from aos_api.extension_runtime.disable_service import RuntimeDisableService
    from aos_api.extension_runtime.generation_attempts import GenerationDrainReader
    from aos_api.extension_runtime.live_installation_scheduler import LiveInstallationScheduler
    from aos_api.extension_runtime.pending_preparation_directory import (
        LiveInstallationOwnerFactory, PostgresPendingPreparationDirectory,
    )
    from aos_api.extension_runtime.preparation_worker import PreparationWorker
    from aos_api.extension_runtime.production_preparation import ProductionPreparationDependencies
    from aos_api.tenant_scope import TenantScope

    if (type(registry) is not SelectedRegistry or type(registry.packages) is not SelectedPackages
            or not callable(registry.connect) or type(installation_reader) is not InstallationService
            or type(preparation) is not SimpleNamespace
            or set(vars(preparation)) != {'dependencies', 'scheduler'}):
        raise ValueError('exact selected runtime control graph required')
    registry.packages.__post_init__()
    deps, scheduler = preparation.dependencies, preparation.scheduler
    if type(deps) is not ProductionPreparationDependencies:
        raise ValueError('original preparation dependencies required')
    deps.__post_init__()
    if (deps.connect is not registry.connect or deps.installation_store._connect_factory is not registry.connect
            or installation_reader._store is not deps.installation_store
            or installation_reader._planning_revalidator is not deps.revalidator
            or deps.policy._trust_roots is not registry.packages.trust_roots
            or deps.platform != 'linux/arm64' or deps.driver.context != 'colima-aos-extension'
            or type(scheduler) is not LiveInstallationScheduler):
        raise ValueError('selected control dependencies differ')
    directory, factory = scheduler.directory, scheduler.factory
    scope = TenantScope('org-org', 'dev-project')
    if (type(directory) is not PostgresPendingPreparationDirectory
            or type(factory) is not LiveInstallationOwnerFactory
            or directory.scope != scope or factory.scope != scope
            or directory.connect is not registry.connect or factory.connect is not registry.connect
            or directory.include_rehydrate is not True or factory.enable_allowed is not True
            or factory.live_directory is not deps.live_directory
            or type(factory.worker) is not PreparationWorker):
        raise ValueError('full selected owner graph required')
    worker = factory.worker
    if (worker.connect is not registry.connect or worker.store is not deps.installation_store
            or worker.revalidator is not deps.revalidator or worker.policy is not deps.policy
            or worker.driver is not deps.driver or worker.platform != deps.platform
            or worker.permission is not deps.apply_permission
            or worker.verification_permission is not deps.verification_permission
            or worker.enable_permission is not deps.enable_permission
            or worker.configuration_authorize is not deps.configuration_authorize):
        raise ValueError('selected control worker graph differs')
    permission = CurrentControlPermission(operation=DISABLE_RUNTIME_OPERATION)
    drain = GenerationDrainReader()
    dependent = EcommerceGrowthDisableDependent()
    configure_service = RuntimeConfigurationService(installation_store=deps.installation_store,
        installation_reader=installation_reader, revalidator=deps.revalidator,
        authorize=deps.configuration_authorize)
    disable_service = RuntimeDisableService(installation_store=deps.installation_store,
        installation_reader=installation_reader, check_current_permission=permission, dependent=dependent)
    configure_consumer = ConfigurationConsumer(connect=registry.connect,
        authorize=deps.configuration_authorize, check_drained=drain)
    disable_consumer = RuntimeDisableConsumer(connect=registry.connect,
        installation_store=deps.installation_store, check_current_permission=permission,
        check_drained=drain, dependent=dependent)
    stage_consumer = ConfigurationStageConsumer(connect=registry.connect,
        authorize=deps.configuration_authorize)
    return SimpleNamespace(stage_consumer=stage_consumer,
        configure_service=configure_service, disable_service=disable_service,
        configure_consumer=configure_consumer, disable_consumer=disable_consumer,
        drain_reader=drain, disable_dependent=dependent)


def build_selected_cutover_control(*, registry, installation_reader, preparation):
    """Compose only the canonical protected registration/cutover channel; never execute."""
    import os
    from aos_api.ecommerce_growth_registration import FirstDispatchRegistrationService
    from aos_api.ecommerce_growth_registration_connection import (
        _CREDENTIAL_FILE, configured_registration_connection, registration_connection,
    )
    from aos_api.ecommerce_growth_cutover import EcommerceGrowthCutoverStore
    from aos_api.ecommerce_growth_cutover_connection import scoped_cutover_connection
    from aos_api.ecommerce_growth_cutover_control import EcommerceGrowthCutoverControl

    build_selected_runtime_control(registry=registry, installation_reader=installation_reader,
        preparation=preparation)
    expected = ROOT / '.evidence' / 'qyh-m2-three-backend-lifecycle-actual-20261023' / 'private' / 'registration-identity.json'
    if os.environ.get(_CREDENTIAL_FILE) != str(expected):
        raise ValueError('fixed isolated registration identity reference required')
    identity_connect = configured_registration_connection()
    if identity_connect is not registration_connection:
        raise TypeError('canonical protected registration connector required')
    deps = preparation.dependencies
    registration = FirstDispatchRegistrationService(connect=identity_connect,
        installation_store=deps.installation_store,
        configuration_authorize=deps.configuration_authorize, release_policy=deps.policy)
    store = EcommerceGrowthCutoverStore(scoped_cutover_connection(identity_connect),
        registration_service=registration)
    control = EcommerceGrowthCutoverControl(store)
    return SimpleNamespace(registration=registration, store=store, control=control)


def build_selected_refresh_history_producer(*, registry, installation_reader, preparation):
    """Compose the original refresh producer graph without executing a phase.

    This is only a fail-closed dependency binding for the future isolated
    two-installation runner. Object construction does not supply registration,
    cutover approval, configuration authority, or a human decision.
    """
    from aos_api.ecommerce_dispatch_configuration_owner import EcommerceDispatchConfigurationOwner
    from aos_api.ecommerce_growth_cutover import EcommerceGrowthCutoverStore
    from aos_api.ecommerce_growth_cutover_control import EcommerceGrowthCutoverControl
    from aos_api.ecommerce_growth_registration import FirstDispatchRegistrationService

    runtime = build_selected_runtime_control(registry=registry,
        installation_reader=installation_reader, preparation=preparation)
    cutover = build_selected_cutover_control(registry=registry,
        installation_reader=installation_reader, preparation=preparation)
    owner = EcommerceDispatchConfigurationOwner()
    dependencies = preparation.dependencies
    if (type(cutover.registration) is not FirstDispatchRegistrationService
            or type(cutover.store) is not EcommerceGrowthCutoverStore
            or type(cutover.control) is not EcommerceGrowthCutoverControl
            or type(owner) is not EcommerceDispatchConfigurationOwner
            or cutover.control._store is not cutover.store
            or cutover.store._registration_service is not cutover.registration
            or cutover.registration._store is not dependencies.installation_store
            or runtime.configure_service._store is not dependencies.installation_store
            or runtime.configure_service._reader is not installation_reader
            or owner._schema != 'public'
            or type(owner._approval) is not EcommerceGrowthCutoverStore):
        raise ValueError('exact selected original refresh producer graph required')
    return SimpleNamespace(runtime=runtime, registration=cutover.registration,
        store=cutover.store, control=cutover.control, owner=owner)


def install_selected_schema_receipts(conn, *, case, preparation, lab_identity):
    """Future isolated bootstrap only: verify physical schema before receipts.

    Caller owns the explicit maintenance transaction and its rollback. This
    function neither migrates nor commits, and cannot target the original DB.
    The future runner must additionally prove endpoint/cluster ownership.
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from aos_api.asset_registry.composition_contracts import ResolvedBundle
    from aos_api.extension_runtime.lifecycle_store import _require_transaction
    from aos_api.extension_runtime.production_preparation import ProductionPreparationDependencies
    from aos_api.extension_runtime.schema_conditions import admit_schema_requirements
    from aos_api.extension_runtime.schema_registry import apply_once

    _require_transaction(conn)
    dependencies = preparation.dependencies
    if (type(dependencies) is not ProductionPreparationDependencies
            or case.scope != dict(org_id='org-org', project_id='dev-project')
            or type(case.registry) is not SelectedRegistry
            or dependencies.installation_store is not case.store
            or dependencies.revalidator is not case.revalidator
            or dependencies.connect is not case.registry.connect
            or dependencies.policy._trust_roots is not case.packages.trust_roots
            or case.packages is not case.registry.packages):
        raise ValueError('exact selected schema dependency graph required')
    case.packages.__post_init__()
    selected = tuple(case.lock.payload.resolved)
    if (len(selected) != 4 or any(type(item) is not ResolvedBundle for item in selected)
            or {(item.publisher, item.id, item.version, item.content_hash) for item in selected}
            != {('aos', bid, version, digest) for bid, (version, digest) in EXPECTED.items()}):
        raise ValueError('exact selected schema lock required')
    identity = verify_selected_lab_identity(conn, lab_identity, maintenance=True)

    # Import only these exact existing public definitions, never its main(),
    # successor selectors, private signing inputs, or old database connector.
    verifier_path = ROOT / 'scripts/a0v_ecommerce_schema_receipts.py'
    raw = verifier_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != '3fd5f2dcf9c01df8737701e406d78e0013e394de49b694ddfe0217fcb3740cfe':
        raise ValueError('physical schema verifier source changed')
    namespace = dict(__name__='m2_selected_schema_definitions', __file__=str(verifier_path))
    exec(compile(raw, str(verifier_path), 'exec'), namespace)
    verify_physical = namespace['verify_physical']
    config = Config()
    config.set_main_option('script_location', str(ROOT / 'services/aos-api/alembic'))
    migration_graph = ScriptDirectory.from_config(config)
    def revisions(head):
        return {node.revision for node in migration_graph.walk_revisions(base='base', head=head)}

    worker = preparation.scheduler.factory.worker
    if worker.store is not case.store or worker.policy is not dependencies.policy:
        raise ValueError('selected schema worker differs from dependency graph')
    pending = []
    for member in selected:
        record = worker.load_record(member)
        requirements = admit_schema_requirements(record=record, selected=member,
            policy=dependencies.policy, checked_at=identity['now'],
            read_artifact=lambda path, limit: worker.read_member_artifact(member, path, limit))
        if member.id not in BACKEND_IDS:
            if requirements:
                raise ValueError('content member cannot introduce schema receipts')
            continue
        raw = worker.read_member_artifact(member, 'artifacts/schema-compatibility.json', 65536)
        if (len(requirements) != 1 or type(raw) is not bytes
                or 'sha256:' + hashlib.sha256(raw).hexdigest() != requirements[0].migration_hash):
            raise ValueError('selected schema compatibility digest differs')
        from aos_api.extension_runtime.ipc import _pairs
        compatibility = json.loads(raw, object_pairs_hook=_pairs)
        if (type(compatibility) is not dict or compatibility.get('bundleId') != member.id
                or type(compatibility.get('schemaVersion')) is not int or compatibility['schemaVersion'] != 1):
            raise ValueError('selected schema compatibility identity differs')
        verify_physical(conn, compatibility, revisions)
        pending.append((member.id, requirements[0], compatibility))
    if len(pending) != 3:
        raise ValueError('exact three schema requirements required')
    result = []
    for bid, requirement, compatibility in pending:
        changed = apply_once(conn, requirement,
            lambda connection, document=compatibility: verify_physical(connection, document, revisions))
        result.append((bid, requirement, changed))
    return tuple(result)


def install_selected_fixture_memberships(conn, *, case, lab_identity):
    """Future new-DB test bootstrap, not a real-person authorization endpoint.

    No upsert, privilege escalation, schema alteration, or commit. The caller
    must prove cluster/endpoint ownership and roll back on any failure.
    """
    from aos_api.extension_runtime.lifecycle_store import _require_transaction
    from aos_api.openfga import user_key

    _require_transaction(conn)
    if (type(case.case_id) is not str
            or re.fullmatch('m2-three-[a-z0-9][a-z0-9-]{0,38}', case.case_id) is None
            or case.scope != dict(org_id='org-org', project_id='dev-project')
            or type(case.registry) is not SelectedRegistry
            or type(case.store) is not PostgresInstallationStore
            or case.store._connect_factory is not case.registry.connect
            or type(case.revalidator) is not RuntimeReleaseRevalidator):
        raise ValueError('exact selected synthetic membership case required')
    author = 'synthetic-' + case.case_id + '-author'
    checker = 'synthetic-' + case.case_id + '-checker'
    verify_selected_lab_identity(conn, lab_identity, maintenance=True)
    if (case.action.get('actor') != author or case.action.get('roles') != ['asset-installer']
            or case.action.get('markings') != []
            or any(case.action.get(k) != v for k, v in case.scope.items())):
        raise ValueError('only the exact synthetic fixture actor is allowed')
    current = case.store.get_installation(**case.scope, installation_id=case.action['installation_id'])
    if (getattr(current.state, 'value', current.state) != 'approved'
            or str(current.installation_id) != str(case.action['installation_id'])
            or current.current.requested_by != author or current.decision is None
            or current.decision.actor != checker or current.decision.decision != 'approved'
            or any(getattr(current.current, field) != getattr(case.lock, field) for field in
                   ('lock_hash', 'permission_diff_hash', 'migration_plan_hash', 'contribution_diff_hash'))):
        raise ValueError('current synthetic approval and duty separation required')
    selected = tuple(case.lock.payload.resolved)
    if (len(selected) != 4
            or {(item.publisher, item.id, item.version, item.content_hash) for item in selected}
            != {('aos', bid, version, digest) for bid, (version, digest) in EXPECTED.items()}):
        raise ValueError('exact four-member membership fixture lock required')
    case.revalidator.revalidate_in_transaction(conn, lock=case.lock)
    if case.lock.payload.permission_diff.target.markings != []:
        raise ValueError('fixed selected fixture does not grant bearer markings')
    tenant = ('org-org', 'dev-project')
    if conn.execute('SELECT 1 AS present FROM meta_workspace WHERE org_id=%s AND project_id=%s FOR KEY SHARE',
                    tenant).fetchone() is None:
        raise ValueError('formal fixture workspace must already exist')
    actors = (author, checker)
    if conn.execute('SELECT subject, role FROM meta_membership WHERE org_id=%s AND project_id=%s '
                    'AND subject=ANY(%s) FOR UPDATE', (*tenant, list(actors))).fetchall():
        raise ValueError('existing fixture membership cannot be overwritten')
    if conn.execute('SELECT user_key FROM authz_tuple WHERE org_id=%s AND project_id=%s '
                    'AND user_key=ANY(%s) FOR UPDATE',
                    (*tenant, [user_key(actor) for actor in actors])).fetchall():
        raise ValueError('existing fixture authorization cannot be reused')
    members = ((author, 'asset-installer'), (checker, 'asset-install-approver'))
    for actor, role in members:
        conn.execute('INSERT INTO meta_membership (org_id, project_id, subject, role, updated_at) '
                     'VALUES (%s,%s,%s,%s,NOW())', (*tenant, actor, role))
    return members


class SelectedPreparationSession:
    """Future isolated live prepare/verify session; construction has no effects.

    Execution needs the separately qualified runner and real fixture bootstrap.
    This is not the production Host identity selector or a business permission.
    """
    def __init__(self, *, case, preparation, lab_identity, timeout_seconds=120,
                 configuration_controls=False):
        from aos_api.extension_runtime.production_preparation import ProductionPreparationDependencies
        from aos_api.extension_runtime.runtime_host import RuntimeHost, RuntimeTenantAssignment
        from aos_api.tenant_scope import TenantScope
        if type(configuration_controls) is not bool or type(lab_identity) is not SelectedLabIdentity:
            raise ValueError('exact selected configuration control mode required')
        deps = preparation.dependencies
        if (type(lab_identity) is not SelectedLabIdentity
                or type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 120
                or type(deps) is not ProductionPreparationDependencies
                or case.scope != dict(org_id='org-org', project_id='dev-project')
                or type(case.lifecycle) is not RuntimeLifecycleService
                or case.lifecycle._store is not case.store or deps.installation_store is not case.store
                or case.lifecycle._revalidator is not case.revalidator or deps.revalidator is not case.revalidator
                or deps.connect is not case.registry.connect
                or case.lifecycle._reader is not case.installation_service
                or case.action['actor'] != 'synthetic-' + case.case_id + '-author'
                or preparation.scheduler.factory.worker.store is not case.store):
            raise ValueError('exact selected preparation session required')
        self.case, self.preparation, self.lab_identity = case, preparation, lab_identity
        self.timeout_seconds = timeout_seconds
        self.scope = TenantScope('org-org', 'dev-project')
        self.controls = (build_selected_runtime_control(registry=case.registry,
            installation_reader=case.installation_service, preparation=preparation)
            if configuration_controls else None)
        consumers = (() if self.controls is None else (
            self.controls.configure_consumer, self.controls.disable_consumer, self.controls.stage_consumer))
        self.assignment = RuntimeTenantAssignment(scope=self.scope, lifecycle=preparation.scheduler,
            consumers=consumers)
        self.host = RuntimeHost(assignments=lambda: (self.assignment,))
        self.task = self.request_context = None
        self._started = self._closing = False
        self._attempted, self._operations = set(), {}
        self._preparation_requests, self._preparation_busy, self._preparation_unknown = {}, False, None
        self._control_requests, self._control_busy, self._control_unknown = {}, False, None

    def _check_database(self):
        from aos_api.extension_runtime.consumer_connection import consumer_connection
        with consumer_connection(self.case.registry.connect, self.case.scope) as conn:
            verify_selected_lab_identity(conn, self.lab_identity, maintenance=False)

    async def start(self):
        import asyncio
        from aos_api.extension_runtime.owned_control_consumer import _settled
        from aos_api.extension_runtime.production_runtime import RuntimeHostSelection
        from starlette.requests import Request
        if self._started or self._closing:
            raise RuntimeError('selected session cannot be restarted')
        self._started = True
        self.stop_event = asyncio.Event()
        try:
            await _settled(asyncio.to_thread(self._check_database))
            pending = await _settled(asyncio.to_thread(self.preparation.scheduler.directory.read_descriptors))
            if pending != ():
                raise RuntimeError('existing live work requires separate reconciliation')
            await _settled(self.host.run_once())
            self.task = asyncio.create_task(self.host.serve(self.stop_event, interval_seconds=1))
            await asyncio.sleep(0)
            if self.task.done():
                await self.task
                raise RuntimeError('selected Host already terminated')
            state = SimpleNamespace(extension_runtime_host_status='ACTIVE', extension_runtime_host_task=self.task,
                extension_runtime_host_selection=RuntimeHostSelection(host=self.host, status='ACTIVE'))
            self.request_context = Request(dict(type='http', app=SimpleNamespace(state=state)))
            return self
        except BaseException:
            await self.close()
            raise

    def admitted(self, kind):
        from aos_api.routers.bundle_runtime_installations import current_preparation_executable
        return (not self._closing and self.request_context is not None
                and current_preparation_executable(self.request_context, **self.case.scope,
                    installation_id=self.case.action['installation_id'], kind=kind))

    def _require_live(self):
        if self._closing or self.task is None or self.task.done():
            raise RuntimeError('selected Host is not live; reconcile, never resend')

    async def request(self, kind, *, freeze_descriptor=None):
        import asyncio
        from aos_api.asset_registry.control_policy import strong_etag
        from aos_api.asset_registry.installation_store import command_request_hash
        from aos_api.extension_runtime.owned_control_consumer import _settled
        if kind not in {'runtime-apply', 'runtime-verify'}:
            raise ValueError('selected session only accepts preparation controls')
        if freeze_descriptor is not None and not callable(freeze_descriptor):
            raise ValueError('descriptor freeze callback must be callable')
        if self._preparation_busy or self._preparation_unknown is not None or kind in self._attempted:
            raise RuntimeError('selected control already attempted or uncertain; reconcile, never resend')
        self._preparation_busy = True
        self._attempted.add(kind)
        try:
            self._require_live()
            if not self.admitted(kind):
                raise RuntimeError('current selected preparation assignment unavailable')
            action = dict(self.case.action)
            if (self.case.scope != dict(org_id='org-org', project_id='dev-project')
                    or set(action) != {'org_id', 'project_id', 'installation_id', 'actor', 'roles', 'markings'}
                    or (action['org_id'], action['project_id']) != self.scope.key
                    or action['actor'] != 'synthetic-' + self.case.case_id + '-author'):
                raise ValueError('selected preparation identity differs')
            for name in ('roles', 'markings'):
                if (type(action[name]) not in (list, tuple)
                        or not all(type(item) is str for item in action[name])):
                    raise ValueError('selected preparation access envelope differs')
            current = await _settled(asyncio.to_thread(self.case.store.get_installation,
                **self.case.scope, installation_id=action['installation_id']))
            self._require_live()
            if_match = strong_etag(current.etag_version)
            key = self.case.case_id + '-' + kind
            descriptor = MappingProxyType(dict(kind=kind,
                namespace='runtime_installations.' + kind, key=key,
                org_id=action['org_id'], project_id=action['project_id'],
                installation=action['installation_id'], actor=action['actor'],
                roles=tuple(action['roles']), markings=tuple(action['markings']),
                if_match=if_match, request_hash=command_request_hash(subject=action['actor'],
                    path_params={'installationId': action['installation_id']},
                    body={'kind': kind}, if_match=if_match)))
            self._preparation_requests[kind] = descriptor
            if freeze_descriptor is not None:
                freeze_descriptor(dict(descriptor))
            self._preparation_unknown = kind
            receipt = await _settled(asyncio.to_thread(self.case.lifecycle.request_preparation,
                **action, kind=kind, idempotency_key=key, if_match=if_match,
                preparation_admission=lambda: self.admitted(kind)))
            operation = self._preparation_receipt(receipt, descriptor, replayed=False)
            self._preparation_requests[kind] = MappingProxyType(
                dict(descriptor, operation=str(operation)))
            self._operations[operation] = kind
            self._preparation_unknown = None
            return operation
        finally:
            self._preparation_busy = False

    def _preparation_receipt(self, receipt, descriptor, *, replayed):
        from uuid import UUID
        from aos_api.asset_registry.control_policy import strong_etag
        from aos_api.asset_registry.installation_store import CommandReceipt
        if (type(receipt) is not CommandReceipt or receipt.status_code != 202
                or receipt.replayed is not replayed or type(receipt.response_json) is not dict):
            raise ValueError('selected preparation receipt differs')
        payload = receipt.response_json
        if (set(payload) != {'installationId', 'operationId', 'phase', 'status', 'revision'}
                or payload['installationId'] != descriptor['installation']
                or payload['phase'] != 'accepted' or payload['status'] != 'accepted'
                or type(payload['revision']) is not int or payload['revision'] < 1
                or type(payload['operationId']) is not str
                or receipt.response_etag != strong_etag(payload['revision'])):
            raise ValueError('selected preparation receipt routing differs')
        operation = UUID(payload['operationId'])
        if str(operation) != payload['operationId']:
            raise ValueError('selected preparation operation differs')
        for other_kind, other in self._preparation_requests.items():
            if other_kind != descriptor['kind'] and other.get('operation') == str(operation):
                raise ValueError('selected preparation operation reused')
        if operation in self._operations and descriptor.get('operation') != str(operation):
            raise ValueError('selected preparation operation already routed')
        return operation

    def _preparation_snapshot(self, descriptor):
        from aos_api.asset_registry.control_policy import parse_strong_if_match
        from aos_api.asset_registry.installation_store import _receipt_from_row, command_request_hash
        from aos_api.extension_runtime.consumer_connection import consumer_connection
        body = {'kind': descriptor['kind']}
        _, revision = parse_strong_if_match(descriptor['if_match'])
        if command_request_hash(subject=descriptor['actor'],
                path_params={'installationId': descriptor['installation']}, body=body,
                if_match=descriptor['if_match']) != descriptor['request_hash']:
            raise ValueError('selected frozen preparation envelope differs')
        scope = dict(org_id=descriptor['org_id'], project_id=descriptor['project_id'])
        if scope != dict(org_id='org-org', project_id='dev-project'):
            raise ValueError('selected preparation observation scope differs')
        with consumer_connection(self.case.registry.connect, scope) as conn:
            verify_selected_lab_identity(conn, self.lab_identity, maintenance=False)
            row = conn.execute('''SELECT subject,request_hash,status_code,response_json,response_etag
                FROM bundle_installation_command WHERE org_id=%s AND project_id=%s
                AND operation=%s AND idempotency_key=%s''',
                (descriptor['org_id'], descriptor['project_id'],
                 descriptor['namespace'], descriptor['key'])).fetchone()
            if row is None:
                raise LookupError('selected preparation outcome unconfirmed; never resend')
            if row['subject'] != descriptor['actor'] or row['request_hash'] != descriptor['request_hash']:
                raise ValueError('selected preparation command history differs')
            operation = self._preparation_receipt(
                _receipt_from_row(row, replayed=True), descriptor, replayed=True)
            row = conn.execute('''SELECT installation_id,kind,requested_by,idempotency_key,
                expected_installation_etag FROM extension_runtime_operation
                WHERE org_id=%s AND project_id=%s AND operation_id=%s''',
                (descriptor['org_id'], descriptor['project_id'], operation)).fetchone()
            if (row is None or str(row['installation_id']) != descriptor['installation']
                    or row['kind'] != descriptor['kind'] or row['requested_by'] != descriptor['actor']
                    or row['idempotency_key'] != descriptor['key']
                    or type(row['expected_installation_etag']) is not int
                    or row['expected_installation_etag'] != revision):
                raise ValueError('selected preparation operation history differs')
            return operation

    async def reconcile_preparation(self, kind):
        import asyncio
        from aos_api.extension_runtime.owned_control_consumer import _settled
        if self._preparation_busy:
            raise RuntimeError('selected preparation still executing')
        if type(kind) is not str or kind not in self._preparation_requests:
            raise ValueError('only this session frozen preparation may be reconciled')
        self._preparation_busy = True
        try:
            descriptor = self._preparation_requests[kind]
            operation = await _settled(asyncio.to_thread(self._preparation_snapshot, descriptor))
            self._preparation_requests[kind] = MappingProxyType(
                dict(descriptor, operation=str(operation)))
            self._operations[operation] = descriptor['kind']
            if self._preparation_unknown == kind:
                self._preparation_unknown = None
            return operation
        finally:
            self._preparation_busy = False

    def _control_context(self):
        from uuid import UUID
        case = self.case
        action = dict(case.action)
        if (type(case.case_id) is not str
                or re.fullmatch('m2-three-[a-z0-9][a-z0-9-]{0,38}', case.case_id) is None
                or case.scope != dict(org_id='org-org', project_id='dev-project')
                or self.scope.key != ('org-org', 'dev-project')
                or set(action) != {'org_id', 'project_id', 'installation_id', 'actor', 'roles', 'markings'}
                or (action['org_id'], action['project_id']) != self.scope.key
                or action['actor'] != 'synthetic-' + case.case_id + '-author'
                or type(action['installation_id']) is not str
                or str(UUID(action['installation_id'])) != action['installation_id']
                or case.store is not self.preparation.dependencies.installation_store
                or case.revalidator is not self.preparation.dependencies.revalidator):
            raise ValueError('selected control identity or dependencies differ')
        for name in ('roles', 'markings'):
            if (type(action[name]) not in (list, tuple)
                    or not all(type(item) is str for item in action[name])):
                raise ValueError('selected control access envelope differs')
            action[name] = tuple(action[name])
        return action, build_selected_runtime_control(registry=case.registry,
            installation_reader=case.installation_service, preparation=self.preparation)

    def _control_receipt(self, receipt, descriptor, *, replayed):
        from uuid import UUID
        from aos_api.asset_registry.installation_store import CommandReceipt
        from aos_api.asset_registry.control_policy import strong_etag
        if (type(receipt) is not CommandReceipt or type(receipt.status_code) is not int
                or receipt.status_code != 202 or receipt.replayed is not replayed
                or type(receipt.response_json) is not dict):
            raise ValueError('selected control receipt differs')
        payload = receipt.response_json
        if (set(payload) != {'installationId', 'operationId', 'phase', 'status', 'revision'}
                or payload['installationId'] != descriptor['installation']
                or type(payload['revision']) is not int or type(payload['operationId']) is not str):
            raise ValueError('selected control receipt routing differs')
        operation = UUID(payload['operationId'])
        expected = {('accepted', 'accepted', 1)}
        if descriptor['kind'] == 'disable':
            expected.add(('fencing', 'running', 2))
        if (str(operation) != payload['operationId']
                or (payload['phase'], payload['status'], payload['revision']) not in expected
                or receipt.response_etag != strong_etag(payload['revision'])):
            raise ValueError('selected control receipt phase differs')
        # A reconciliation may observe its own known receipt, never another intent's.
        for intent, other in self._control_requests.items():
            if intent != descriptor['intent'] and other.get('operation') == str(operation):
                raise ValueError('selected control operation reused')
        if operation in self._operations and descriptor.get('operation') != str(operation):
            raise ValueError('selected control operation already routed')
        return operation

    async def request_control(self, *, intent, target, freeze_descriptor=None):
        import asyncio
        from aos_api.asset_registry.control_policy import (
            CONFIGURE_RUNTIME_OPERATION, ENABLE_RUNTIME_OPERATION, DISABLE_RUNTIME_OPERATION, strong_etag)
        from aos_api.asset_registry.installation_store import command_request_hash
        from aos_api.extension_runtime.configuration_contracts import ConfigureTarget
        from aos_api.extension_runtime.disable_contracts import DisableTarget
        from aos_api.extension_runtime.owned_control_consumer import _settled
        intents = {'configure-initial': 'configure', 'enable-initial': 'enable',
            'disable-deny': 'disable', 'configure-restored': 'configure',
            'enable-restored': 'enable', 'disable-retire': 'disable'}
        if type(intent) is not str or intent not in intents:
            raise ValueError('fixed selected control intent required')
        if freeze_descriptor is not None and not callable(freeze_descriptor):
            raise ValueError('descriptor freeze callback must be callable')
        if self._control_busy or self._control_unknown is not None or intent in self._attempted:
            raise RuntimeError('selected control attempted or uncertain; reconcile, never resend')
        self._require_live()
        if self.controls is None:
            raise RuntimeError('selected configuration controls unavailable')
        self._control_busy = True
        self._attempted.add(intent)
        try:
            kind = intents[intent]
            model = DisableTarget if kind == 'disable' else ConfigureTarget
            frozen = model.model_validate(target)
            action, graph = self._control_context()
            await _settled(asyncio.to_thread(self._check_database))
            current = await _settled(asyncio.to_thread(self.case.store.get_installation,
                org_id=action['org_id'], project_id=action['project_id'],
                installation_id=action['installation_id']))
            self._require_live()
            if_match = strong_etag(current.etag_version)
            target_json = frozen.model_dump(mode='json')
            body = {'target': target_json}
            if kind != 'disable':
                body['kind'] = kind
            descriptor = MappingProxyType(dict(intent=intent, kind=kind,
                namespace={'configure': CONFIGURE_RUNTIME_OPERATION, 'enable': ENABLE_RUNTIME_OPERATION,
                           'disable': DISABLE_RUNTIME_OPERATION}[kind],
                key=self.case.case_id + '-' + intent, org_id=action['org_id'], project_id=action['project_id'],
                installation=action['installation_id'], actor=action['actor'],
                roles=action['roles'], markings=action['markings'],
                target_json=json.dumps(target_json, sort_keys=True, separators=(',', ':')),
                if_match=if_match, request_hash=command_request_hash(subject=action['actor'],
                    path_params={'installationId': action['installation_id']}, body=body, if_match=if_match)))
            self._control_requests[intent] = descriptor
            if freeze_descriptor is not None:
                freeze_descriptor(dict(descriptor))
            self._control_unknown = intent
            kwargs = dict(**action, idempotency_key=descriptor['key'], if_match=if_match, target=frozen)
            service = graph.disable_service if kind == 'disable' else graph.configure_service
            if kind != 'disable':
                kwargs['kind'] = kind
            receipt = await _settled(asyncio.to_thread(service.request, **kwargs))
            operation = self._control_receipt(receipt, descriptor, replayed=False)
            self._control_requests[intent] = MappingProxyType(dict(descriptor, operation=str(operation)))
            self._operations[operation] = kind
            self._control_unknown = None
            return operation
        finally:
            self._control_busy = False

    def _control_snapshot(self, descriptor):
        from uuid import UUID
        from aos_api.asset_registry.control_policy import parse_strong_if_match
        from aos_api.asset_registry.installation_store import _receipt_from_row, command_request_hash
        from aos_api.extension_runtime.configuration_request import load_configure_target, load_enable_target
        from aos_api.extension_runtime.disable_request import load_disable_target
        from aos_api.extension_runtime.consumer_connection import consumer_connection
        target = json.loads(descriptor['target_json'])
        body = {'target': target}
        if descriptor['kind'] != 'disable':
            body['kind'] = descriptor['kind']
        _, revision = parse_strong_if_match(descriptor['if_match'])
        if command_request_hash(subject=descriptor['actor'],
                path_params={'installationId': descriptor['installation']}, body=body,
                if_match=descriptor['if_match']) != descriptor['request_hash']:
            raise ValueError('selected frozen command envelope differs')
        scope = dict(org_id=descriptor['org_id'], project_id=descriptor['project_id'])
        if scope != dict(org_id='org-org', project_id='dev-project'):
            raise ValueError('selected control observation scope differs')
        with consumer_connection(self.case.registry.connect, scope) as conn:
            verify_selected_lab_identity(conn, self.lab_identity, maintenance=False)
            row = conn.execute('''SELECT subject,request_hash,status_code,response_json,response_etag
                FROM bundle_installation_command WHERE org_id=%s AND project_id=%s
                AND operation=%s AND idempotency_key=%s''',
                (descriptor['org_id'], descriptor['project_id'], descriptor['namespace'], descriptor['key'])).fetchone()
            if row is None:
                raise LookupError('selected command outcome unconfirmed; never resend')
            if row['subject'] != descriptor['actor'] or row['request_hash'] != descriptor['request_hash']:
                raise ValueError('selected command history differs')
            operation = self._control_receipt(_receipt_from_row(row, replayed=True), descriptor, replayed=True)
            row = conn.execute('''SELECT installation_id,kind,requested_by,idempotency_key,expected_installation_etag
                FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND operation_id=%s''',
                (descriptor['org_id'], descriptor['project_id'], operation)).fetchone()
            if (row is None or str(row['installation_id']) != descriptor['installation']
                    or row['kind'] != descriptor['kind'] or row['requested_by'] != descriptor['actor']
                    or row['idempotency_key'] != descriptor['key']
                    or type(row['expected_installation_etag']) is not int
                    or row['expected_installation_etag'] != revision):
                raise ValueError('selected command operation history differs')
            loader = {'configure': load_configure_target, 'enable': load_enable_target,
                      'disable': load_disable_target}[descriptor['kind']]
            accepted = loader(conn, **scope, operation_id=UUID(str(operation)))
            if accepted.model_dump(mode='json') != target:
                raise ValueError('selected immutable accepted target differs')
            return operation

    async def reconcile_control(self, *, intent):
        import asyncio
        from aos_api.extension_runtime.owned_control_consumer import _settled
        if self._control_busy:
            raise RuntimeError('selected control still executing')
        if type(intent) is not str or intent not in self._control_requests:
            raise ValueError('only this session frozen command may be reconciled')
        self._control_busy = True
        try:
            descriptor = self._control_requests[intent]
            operation = await _settled(asyncio.to_thread(self._control_snapshot, descriptor))
            self._control_requests[intent] = MappingProxyType(dict(descriptor, operation=str(operation)))
            self._operations[operation] = descriptor['kind']
            if self._control_unknown == intent:
                self._control_unknown = None
            return operation
        finally:
            self._control_busy = False

    def _operation_snapshot(self, operation):
        from aos_api.extension_runtime.consumer_connection import consumer_connection
        with consumer_connection(self.case.registry.connect, self.case.scope) as conn:
            return conn.execute('''SELECT o.installation_id,o.kind,o.status,
                count(b.event_id) FILTER (WHERE b.delivered_at IS NULL) AS pending
                FROM extension_runtime_operation o
                LEFT JOIN extension_runtime_event e ON (e.org_id,e.project_id,e.operation_id)=
                    (o.org_id,o.project_id,o.operation_id)
                LEFT JOIN extension_runtime_outbox b ON (b.org_id,b.project_id,b.event_id)=
                    (e.org_id,e.project_id,e.event_id) AND b.consumer_id='runtime-reconciler'
                WHERE o.org_id=%s AND o.project_id=%s AND o.operation_id=%s
                GROUP BY o.installation_id,o.kind,o.status''',
                (*self.scope.key, operation)).fetchone()

    async def wait_operation(self, operation, *, kind):
        import asyncio
        from aos_api.extension_runtime.owned_control_consumer import _settled
        self._require_live()
        if self._operations.get(operation) != kind:
            raise ValueError('only this session accepted operation may be observed')
        deadline = asyncio.get_running_loop().time() + self.timeout_seconds
        while True:
            self._require_live()
            row = await _settled(asyncio.to_thread(self._operation_snapshot, operation))
            if (row is None or str(row['installation_id']) != self.case.action['installation_id']
                    or row['kind'] != kind):
                raise ValueError('selected operation observation routing differs')
            if row['status'] in {'failed', 'cancelled', 'needs_attention'}:
                raise RuntimeError('selected operation failed; reconcile, never resend')
            if row['status'] == 'succeeded' and row['pending'] == 0:
                return row
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError('selected operation observation timed out; no resend')
            await asyncio.sleep(.05)

    async def prepare_and_verify(self):
        import asyncio
        from uuid import UUID
        from aos_api.extension_runtime.live_installation_owner import LiveInstallationLifecycleOwner
        from aos_api.extension_runtime.preparation_worker import PreparedJob
        from aos_api.extension_runtime.owned_control_consumer import _settled
        apply = await self.request('runtime-apply')
        await self.wait_operation(apply, kind='runtime-apply')
        applied = await _settled(asyncio.to_thread(self.case.store.get_installation,
            **self.case.scope, installation_id=self.case.action['installation_id']))
        if applied.state != 'applied' or applied.active_revision is not None:
            raise ValueError('selected preparation did not persist applied state')
        verify = await self.request('runtime-verify')
        await self.wait_operation(verify, kind='runtime-verify')
        active = await _settled(asyncio.to_thread(self.case.store.get_installation,
            **self.case.scope, installation_id=self.case.action['installation_id']))
        if active.state != 'active' or active.active_revision != active.current_revision:
            raise ValueError('selected verification did not persist active pointer')
        owner = self.preparation.scheduler.find_owner(UUID(self.case.action['installation_id']))
        if type(owner) is not LiveInstallationLifecycleOwner or type(owner.preparation.job) is not PreparedJob:
            raise ValueError('selected verified live owner missing')
        job = owner.preparation.job
        if (job.plan.installation_id != UUID(self.case.action['installation_id'])
                or len(job.plan.members) != 3
                or {(x.selected.id, x.selected.content_hash) for x in job.plan.members}
                != {(bid, EXPECTED[bid][1]) for bid in BACKEND_IDS}
                or len({x.intent.resource_id for x in job.plan.members}) != 3):
            raise ValueError('selected live three-member resource identity differs')
        await _settled(job.check_health())
        return SimpleNamespace(installation=active, job=job, apply_operation=apply, verify_operation=verify)

    async def _wait_host(self):
        import asyncio
        return await asyncio.shield(self.task)

    async def close(self):
        from aos_api.extension_runtime.owned_control_consumer import _settled
        if self._closing:
            if self.task is not None:
                await _settled(self._wait_host())
            return
        self._closing = True
        if self.request_context is not None:
            self.request_context.app.state.extension_runtime_host_status = 'INACTIVE'
        if self.task is not None:
            self.stop_event.set()
            await _settled(self._wait_host())
        else:
            await _settled(self.host.stop())

    async def __aenter__(self):
        return await self.start()

    async def __aexit__(self, *_error):
        await self.close()


class SelectedInitialActivationSequence:
    """Strict initial apply/verify/configure/enable orchestration.

    This composes the original services owned by SelectedPreparationSession. It
    never turns a timeout into permission to issue a second command.
    """
    _STEPS = ('runtime-apply', 'runtime-verify', 'configure-initial', 'enable-initial')

    def __init__(self, *, session, configuration_target, deferred_configuration=False):
        from aos_api.extension_runtime.configuration_contracts import ConfigureTarget
        if type(session) is not SelectedPreparationSession or session.controls is None:
            raise ValueError('full selected preparation session required')
        if type(deferred_configuration) is not bool or (deferred_configuration and configuration_target is not None):
            raise ValueError('explicit unbound configuration mode required')
        target = None if deferred_configuration else ConfigureTarget.model_validate(configuration_target)
        self.session = session
        self._configure_target = None if target is None else target.model_dump(mode='json')
        self._enable_target = None
        self._position = 0
        self._pending = None
        self._operations = []
        self._busy = False
        self._installation = self._job = self._binding = None

    async def bind_configuration_target(self, target):
        """Bind a staged ref after the original worker has created its generation."""
        import asyncio
        from uuid import UUID
        from aos_api.extension_runtime.configuration_contracts import ConfigureTarget
        from aos_api.extension_runtime.configuration_store import read_configuration
        from aos_api.extension_runtime.consumer_connection import consumer_connection
        from aos_api.extension_runtime.owned_control_consumer import _settled
        from aos_api.extension_runtime.preparation_worker import PreparedJob
        if self._configure_target is not None:
            raise RuntimeError('configuration target already bound')
        if (self._busy or self._position != 2 or self._pending is not None
                or self.session._preparation_unknown is not None or self.session._control_unknown is not None):
            raise RuntimeError('settled original preparation required before configuration target')
        checked = ConfigureTarget.model_validate(target)
        job, session = self._job, self.session
        session._require_live()
        if (type(job) is not PreparedJob or not job._verified
                or job.plan.generation != UUID(checked.generation)
                or job.plan.installation_id != UUID(session.case.action['installation_id'])):
            raise ValueError('configuration target differs from verified preparation')
        self._busy = True
        try:
            def read():
                action, _graph = session._control_context()
                with consumer_connection(session.case.registry.connect, session.case.scope) as conn:
                    verify_selected_lab_identity(conn, session.lab_identity, maintenance=False)
                    read_configuration(conn, **session.case.scope,
                        installation_id=session.case.action['installation_id'], generation=checked.generation,
                        actor=action['actor'], ref=checked.configRef,
                        authorize=session.preparation.dependencies.configuration_authorize)
            await _settled(asyncio.to_thread(read))
            binding = await self._binding_snapshot(checked.generation)
            session._require_live()
            if (binding is None or str(binding['generation']) != checked.generation
                    or type(binding['revision']) is not int or binding['revision'] != checked.bindingRevision
                    or binding['enabled'] is not False or binding['operation_fence'] is not True
                    or binding['desired_state'] != 'disabled' or binding['observed_state'] != 'ready'):
                raise ValueError('configuration target binding is no longer current and fenced')
            self._configure_target = checked.model_dump(mode='json')
        finally:
            self._busy = False

    async def prepare_initial(self):
        """Run only the two original preparation steps; no configure or enable."""
        if self._position > 2:
            raise RuntimeError('initial preparation boundary already passed')
        return await self._run_until(2)

    @property
    def position(self):
        return self._position

    @property
    def pending_operation(self):
        return None if self._pending is None else self._pending[1]

    def _step(self):
        return None if self._position == len(self._STEPS) else self._STEPS[self._position]

    @staticmethod
    def _operation_kind(step):
        return {'configure-initial': 'configure', 'enable-initial': 'enable'}.get(step, step)

    async def _issue(self, step, *, freeze_descriptor=None):
        if step in {'runtime-apply', 'runtime-verify'}:
            if freeze_descriptor is None:
                return await self.session.request(step)
            return await self.session.request(step, freeze_descriptor=freeze_descriptor)
        target = self._configure_target if step == 'configure-initial' else self._enable_target
        if target is None:
            raise RuntimeError('current configuration target required before configure or enable')
        if freeze_descriptor is None:
            return await self.session.request_control(intent=step, target=target)
        return await self.session.request_control(
            intent=step, target=target, freeze_descriptor=freeze_descriptor)

    async def _binding_snapshot(self, generation):
        import asyncio
        from uuid import UUID
        from aos_api.extension_runtime.consumer_connection import consumer_connection
        from aos_api.extension_runtime.owned_control_consumer import _settled
        session = self.session

        def read():
            with consumer_connection(session.case.registry.connect, session.case.scope) as conn:
                verify_selected_lab_identity(conn, session.lab_identity, maintenance=False)
                return conn.execute('''SELECT generation,revision,config_ref,enabled,operation_fence,
                    desired_state,observed_state FROM extension_runtime_binding
                    WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s''',
                    (*session.scope.key, UUID(session.case.action['installation_id']), UUID(generation))).fetchone()

        return await _settled(asyncio.to_thread(read))

    async def _validate_step(self, step):
        import asyncio
        from uuid import UUID
        from aos_api.extension_runtime.live_installation_owner import LiveInstallationLifecycleOwner
        from aos_api.extension_runtime.preparation_worker import PreparedJob
        from aos_api.extension_runtime.owned_control_consumer import _settled
        session = self.session
        if step in {'runtime-apply', 'runtime-verify'}:
            current = await _settled(asyncio.to_thread(session.case.store.get_installation,
                **session.case.scope, installation_id=session.case.action['installation_id']))
            state = getattr(current.state, 'value', current.state)
            if step == 'runtime-apply':
                if state != 'applied' or current.active_revision is not None:
                    raise ValueError('selected preparation did not persist applied state')
                return current
            if state != 'active' or current.active_revision != current.current_revision:
                raise ValueError('selected verification did not persist active pointer')
            owner = session.preparation.scheduler.find_owner(UUID(session.case.action['installation_id']))
            if type(owner) is not LiveInstallationLifecycleOwner or type(owner.preparation.job) is not PreparedJob:
                raise ValueError('selected verified live owner missing')
            job = owner.preparation.job
            if (job.plan.installation_id != UUID(session.case.action['installation_id'])
                    or len(job.plan.members) != 3
                    or {(x.selected.id, x.selected.content_hash) for x in job.plan.members}
                    != {(bid, EXPECTED[bid][1]) for bid in BACKEND_IDS}
                    or len({x.intent.resource_id for x in job.plan.members}) != 3):
                raise ValueError('selected live three-member resource identity differs')
            await _settled(job.check_health())
            return current, job
        target = self._configure_target if step == 'configure-initial' else self._enable_target
        row = await self._binding_snapshot(target['generation'])
        if (row is None or str(row['generation']) != target['generation']
                or row['config_ref'] != target['configRef'] or type(row['revision']) is not int):
            raise ValueError('selected activation binding identity differs')
        if step == 'configure-initial':
            if (row['revision'] != target['bindingRevision'] + 2 or row['enabled'] is not False
                    or row['operation_fence'] is not True or row['desired_state'] != 'disabled'
                    or row['observed_state'] != 'unknown'):
                raise ValueError('selected configured binding differs')
        elif (row['revision'] != target['bindingRevision'] + 1 or row['enabled'] is not True
                or row['operation_fence'] is not False or row['desired_state'] != 'enabled'
                or row['observed_state'] != 'ready'):
            raise ValueError('selected enabled binding differs')
        return dict(row)

    async def _settle_pending(self):
        step, operation = self._pending
        await self.session.wait_operation(operation, kind=self._operation_kind(step))
        fact = await self._validate_step(step)
        if step == 'runtime-verify':
            self._installation, self._job = fact
        elif step == 'configure-initial':
            self._binding = fact
            self._enable_target = dict(generation=fact['generation'], bindingRevision=fact['revision'],
                configRef=self._configure_target['configRef'])
        elif step == 'enable-initial':
            self._binding = fact
        self._operations.append(operation)
        self._pending = None
        self._position += 1

    async def run(self):
        return await self._run_until(len(self._STEPS))

    async def _run_until(self, stop_position):
        if self._busy:
            raise RuntimeError('selected activation sequence already executing')
        self._busy = True
        try:
            while self._position < stop_position:
                step = self._step()
                if self._pending is None:
                    if self.session._preparation_unknown is not None or self.session._control_unknown is not None:
                        raise RuntimeError('selected activation outcome uncertain; reconcile, never resend')
                    operation = await self._issue(step)
                    self._pending = (step, operation)
                await self._settle_pending()
            return SimpleNamespace(operations=tuple(self._operations), installation=self._installation,
                job=self._job, binding=self._binding)
        finally:
            self._busy = False

    async def reconcile_unknown(self):
        if self._busy or self._pending is not None:
            raise RuntimeError('selected activation already has an operation to observe')
        step = self._step()
        if step is None:
            raise RuntimeError('selected activation sequence already complete')
        self._busy = True
        try:
            if step in {'runtime-apply', 'runtime-verify'}:
                if self.session._preparation_unknown != step:
                    raise ValueError('current preparation unknown does not match sequence')
                operation = await self.session.reconcile_preparation(step)
            else:
                if self.session._control_unknown != step:
                    raise ValueError('current control unknown does not match sequence')
                operation = await self.session.reconcile_control(intent=step)
            self._pending = (step, operation)
            await self._settle_pending()
            return operation
        finally:
            self._busy = False
