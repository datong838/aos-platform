import pytest
from aos_api.aip_route_worker_identity import (
    RouteWorkerIdentityBlocked,
    RouteWorkerIdentityConfig,
    RouteWorkerIdentityProvider,
    WorkerTokenResponse,
)
from aos_api.aip_route_worker_installation import (
    RouteWorkerIdentityInstallation,
    RouteWorkerIdentityInstallationStore,
    RouteWorkerSignedRelease,
    release_set_hash,
)
from aos_api.auth import Principal
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
NOW = 1_800_000_000
TOKEN = "header.payload.signature"


class Secrets:
    def __init__(self, *, exists=True):
        self.locators = []
        self.item_exists = exists

    def read(self, locator):
        self.locators.append(locator)
        return "machine-secret"

    def exists(self, locator):
        self.locators.append(locator)
        return self.item_exists


class Transport:
    def __init__(self, response=None):
        self.response = response or WorkerTokenResponse(
            200,
            {
                "access_token": TOKEN,
                "token_type": "Bearer",
                "expires_in": 300,
            },
        )
        self.calls = []

    def exchange(self, endpoint, form):
        self.calls.append((endpoint, form))
        return self.response


def config():
    return RouteWorkerIdentityConfig(
        issuer="http://127.0.0.1:18448/realms/qyh-local",
        audience="aos-api",
        token_endpoint=(
            "http://127.0.0.1:18448/realms/qyh-local/protocol/openid-connect/token"
        ),
        client_id="aos-route-worker",
        expected_subject="service-account-aos-route-worker",
        secret_version="v1",
    )


def test_default_identity_backend_uses_platform_factory(monkeypatch):
    secrets = Secrets()
    monkeypatch.setattr(
        "aos_api.aip_route_worker_identity.default_secret_client", lambda: secrets
    )

    provider = RouteWorkerIdentityProvider(config=config(), transport=Transport())

    assert provider._secret_client is secrets


def claims(**updates):
    value = {
        "sub": "service-account-aos-route-worker",
        "iss": config().issuer,
        "aud": "aos-api",
        "org_id": "org-org",
        "project_id": "dev-project",
        "roles": ["aos_route_worker"],
        "iat": NOW,
        "exp": NOW + 300,
    }
    value.update(updates)
    return value


def test_acquires_one_short_lived_service_identity_without_exposing_secret(monkeypatch):
    secret_client, transport = Secrets(), Transport()
    monkeypatch.setattr(
        "aos_api.aip_route_worker_identity.verify_access_token", lambda token: claims()
    )
    monkeypatch.setattr(
        "aos_api.aip_route_worker_identity.resolve_principal",
        lambda **kw: Principal(
            subject="service-account-aos-route-worker",
            org_id="org-org",
            project_id="dev-project",
            roles=["aos_route_worker"],
            token_kind="oidc",
        ),
    )
    provider = RouteWorkerIdentityProvider(
        config=config(),
        secret_client=secret_client,
        transport=transport,
        clock=lambda: NOW,
    )
    context = provider.acquire(SCOPE)
    assert context.principal.subject == "service-account-aos-route-worker"
    assert context.bearer_token.get_secret_value() == TOKEN
    assert len(transport.calls) == 1
    assert transport.calls[0][1] == {
        "grant_type": "client_credentials",
        "client_id": "aos-route-worker",
        "client_secret": "machine-secret",
    }
    assert secret_client.locators[0].account.endswith("client-secret/v1")
    assert TOKEN not in repr(context) and "machine-secret" not in repr(context)


def test_startup_probe_checks_exact_secret_version_without_reading_or_exchanging():
    secret_client, transport = Secrets(), Transport()
    provider = RouteWorkerIdentityProvider(
        config=config(),
        secret_client=secret_client,
        transport=transport,
        clock=lambda: NOW,
    )
    provider.assert_configured(SCOPE)
    assert len(secret_client.locators) == 1
    assert secret_client.locators[0].account == (
        "org-org/dev-project/aos-route-worker/client-secret/v1"
    )
    assert transport.calls == []


def test_startup_probe_fails_closed_when_exact_secret_version_is_missing():
    provider = RouteWorkerIdentityProvider(
        config=config(),
        secret_client=Secrets(exists=False),
        transport=Transport(),
        clock=lambda: NOW,
    )
    with pytest.raises(
        RouteWorkerIdentityBlocked, match="ROUTE_WORKER_CURRENT_IDENTITY_REQUIRED"
    ):
        provider.assert_configured(SCOPE)


@pytest.mark.parametrize(
    "bad_claim",
    [
        {"sub": "operator"},
        {"roles": ["developer"]},
        {"org_id": "dev-org"},
        {"aud": "other"},
        {"exp": NOW + 901},
        {"iat": NOW + 60},
    ],
)
def test_rejects_noncurrent_or_overlong_service_identity(monkeypatch, bad_claim):
    monkeypatch.setattr(
        "aos_api.aip_route_worker_identity.verify_access_token",
        lambda token: claims(**bad_claim),
    )
    monkeypatch.setattr(
        "aos_api.aip_route_worker_identity.resolve_principal",
        lambda **kw: pytest.fail("principal must not be built"),
    )
    with pytest.raises(
        RouteWorkerIdentityBlocked, match="ROUTE_WORKER_CURRENT_IDENTITY_REQUIRED"
    ):
        RouteWorkerIdentityProvider(
            config=config(),
            secret_client=Secrets(),
            transport=Transport(),
            clock=lambda: NOW,
        ).acquire(SCOPE)


def test_token_exchange_failure_is_not_retried(monkeypatch):
    transport = Transport(WorkerTokenResponse(503, {"error": "unavailable"}))
    monkeypatch.setattr(
        "aos_api.aip_route_worker_identity.verify_access_token",
        lambda token: pytest.fail("invalid exchange must not verify"),
    )
    with pytest.raises(RouteWorkerIdentityBlocked):
        RouteWorkerIdentityProvider(
            config=config(),
            secret_client=Secrets(),
            transport=transport,
            clock=lambda: NOW,
        ).acquire(SCOPE)
    assert len(transport.calls) == 1


def test_environment_requires_exact_external_keycloak_endpoint(monkeypatch):
    values = {
        "AOS_AUTH_EXTERNAL_ONLY": "1",
        "AOS_AUTH_ALLOW_DEV": "0",
        "AOS_OIDC_ISSUER": config().issuer,
        "AOS_OIDC_AUDIENCE": "aos-api",
        "AOS_OIDC_TOKEN_URL": config().token_endpoint,
        "AOS_ROUTE_WORKER_OIDC_CLIENT_ID": "aos-route-worker",
        "AOS_ROUTE_WORKER_OIDC_SUBJECT": "service-account-aos-route-worker",
        "AOS_ROUTE_WORKER_OIDC_SECRET_VERSION": "v1",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    assert RouteWorkerIdentityConfig.from_env() == config()
    monkeypatch.setenv("AOS_OIDC_TOKEN_URL", "https://attacker.example/token")
    with pytest.raises(RouteWorkerIdentityBlocked):
        RouteWorkerIdentityConfig.from_env()


def test_environment_can_load_one_atomic_protected_installation(tmp_path, monkeypatch):
    releases = (
        RouteWorkerSignedRelease(
            publisher="aos.local",
            bundleId="ecommerce-growth",
            version="1.13.0",
            contentHash="sha256:" + "b" * 64,
            signatureFingerprint="sha256:" + "c" * 64,
            releaseEvidenceRevision="release-7",
        ),
    )
    installed = RouteWorkerIdentityInstallation(
        schemaVersion="aos.route-worker-identity-installation/v1",
        orgId="org-org",
        projectId="dev-project",
        issuer=config().issuer,
        audience=config().audience,
        tokenEndpoint=config().token_endpoint,
        clientId=config().client_id,
        expectedSubject=config().expected_subject,
        secretVersion=config().secret_version,
        installationId="00000000-0000-0000-0000-000000000107",
        installationRevision=7,
        installationEtag=7,
        lockHash="sha256:" + "a" * 64,
        releases=releases,
        releaseSetHash=release_set_hash(releases),
    )
    path = tmp_path / "route-worker.json"
    RouteWorkerIdentityInstallationStore(secret_client=Secrets()).install(
        path, installed
    )
    values = {
        "AOS_AUTH_EXTERNAL_ONLY": "1",
        "AOS_AUTH_ALLOW_DEV": "0",
        "AOS_OIDC_ISSUER": config().issuer,
        "AOS_OIDC_AUDIENCE": config().audience,
        "AOS_OIDC_TOKEN_URL": config().token_endpoint,
        "AOS_ROUTE_WORKER_IDENTITY_FILE": str(path),
        # Drifting legacy route-specific values must not create a mixed document.
        "AOS_ROUTE_WORKER_OIDC_CLIENT_ID": "legacy-drift",
        "AOS_ROUTE_WORKER_OIDC_SUBJECT": "legacy-drift",
        "AOS_ROUTE_WORKER_OIDC_SECRET_VERSION": "legacy-drift",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    assert RouteWorkerIdentityConfig.from_env() == config()

    monkeypatch.setenv("AOS_OIDC_AUDIENCE", "different-audience")
    with pytest.raises(RouteWorkerIdentityBlocked):
        RouteWorkerIdentityConfig.from_env()


def test_file_installation_is_revalidated_before_secret_probe(tmp_path, monkeypatch):
    releases = (
        RouteWorkerSignedRelease(
            publisher="aos.local",
            bundleId="ecommerce-growth",
            version="1.13.0",
            contentHash="sha256:" + "b" * 64,
            signatureFingerprint="sha256:" + "c" * 64,
            releaseEvidenceRevision="release-7",
        ),
    )
    installed = RouteWorkerIdentityInstallation(
        orgId="org-org",
        projectId="dev-project",
        issuer=config().issuer,
        audience=config().audience,
        tokenEndpoint=config().token_endpoint,
        clientId=config().client_id,
        expectedSubject=config().expected_subject,
        secretVersion=config().secret_version,
        installationId="00000000-0000-0000-0000-000000000107",
        installationRevision=7,
        installationEtag=7,
        lockHash="sha256:" + "a" * 64,
        releases=releases,
        releaseSetHash=release_set_hash(releases),
    )
    path = tmp_path / "route-worker.json"
    RouteWorkerIdentityInstallationStore(secret_client=Secrets()).install(
        path, installed
    )
    for name, value in {
        "AOS_AUTH_EXTERNAL_ONLY": "1",
        "AOS_AUTH_ALLOW_DEV": "0",
        "AOS_OIDC_ISSUER": config().issuer,
        "AOS_OIDC_AUDIENCE": config().audience,
        "AOS_OIDC_TOKEN_URL": config().token_endpoint,
        "AOS_ROUTE_WORKER_IDENTITY_FILE": str(path),
    }.items():
        monkeypatch.setenv(name, value)

    class Authority:
        def __init__(self):
            self.calls = []

        def assert_current(self, value):
            self.calls.append(value)
            return True

    authority, secrets = Authority(), Secrets()
    provider = RouteWorkerIdentityProvider(
        config=RouteWorkerIdentityConfig.from_env(),
        secret_client=secrets,
        transport=Transport(),
        installation_authority=authority,
        clock=lambda: NOW,
    )
    provider.assert_configured(SCOPE)
    assert authority.calls == [installed]
    assert len(secrets.locators) == 1
