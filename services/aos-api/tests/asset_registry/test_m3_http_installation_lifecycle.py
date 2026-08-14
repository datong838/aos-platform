"""M3 final HTTP lifecycle through real auth, router, service, and PostgreSQL."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.asset_registry.installation_revalidation import RevalidationResult
from aos_api.asset_registry.installation_service import InstallationService
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.errors import register_exception_handlers
from aos_api.routers import auth_oidc, bundle_installations
from tests.asset_registry.test_installation_store import (
    ORG,
    PROJECT,
    _isolated_schema,
    _seed_composition,
)


class _ControlClockRevalidator:
    """Keep this HTTP test deterministic after the lock has been seeded."""

    def revalidate_in_transaction(self, conn, *, lock):
        _ = lock
        checked_at = conn.execute(
            "SELECT clock_timestamp() AS checked_at"
        ).fetchone()["checked_at"]
        return RevalidationResult(checked_at=checked_at)


def _application(service: InstallationService) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(auth_oidc.router)
    app.include_router(bundle_installations.router)
    app.dependency_overrides[bundle_installations.get_installation_service] = (
        lambda: service
    )
    return app


def _token(
    client: TestClient,
    *,
    subject: str,
    roles: list[str],
) -> str:
    response = client.post(
        "/v1/auth/token",
        json={
            "grantType": "dev",
            "subject": subject,
            "orgId": ORG,
            "projectId": PROJECT,
            "roles": roles,
            "markings": ["public"],
            "alg": "HS256",
        },
    )
    assert response.status_code == 200
    return response.json()["accessToken"]


def _headers(token: str, **extra: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Org-Id": ORG,
        "X-Project-Id": PROJECT,
        **extra,
    }


def _assert_installation_response(
    response,
    *,
    state: str,
    revision: int,
) -> dict:
    assert response.status_code in {200, 201}, response.text
    assert response.headers["etag"] == f'"{revision}"'
    body = response.json()
    assert body["state"] == state
    assert body["currentRevision"] == revision
    assert body["etagVersion"] == revision
    assert body["current"]["revision"] == revision
    assert body["current"]["state"] == state
    assert len(body["events"]) == revision
    return body


def test_m3_http_installation_lifecycle_with_real_jwt_and_postgres(
    monkeypatch,
) -> None:
    monkeypatch.setenv("AOS_AUTH_ALLOW_DEV", "1")
    with _isolated_schema() as scoped_connect:
        @contextmanager
        def request_safe_scoped_connect():
            # The request scope normally makes db.connect() activate the
            # production runtime role.  This disposable schema deliberately
            # predates RLS adoption, so let the Asset Store bind its own GUCs.
            with (
                patch("aos_api.db.current_tenant_scope", return_value=None),
                scoped_connect() as conn,
            ):
                yield conn

        composition_store = PostgresCompositionStore(request_safe_scoped_connect)
        installation_store = PostgresInstallationStore(request_safe_scoped_connect)
        lock = _seed_composition(composition_store)
        service = InstallationService(
            store=installation_store,
            composition_store=composition_store,
            revalidator=_ControlClockRevalidator(),
        )

        with (
            patch("aos_api.tenant_directory_service.require_workspace"),
            TestClient(_application(service), raise_server_exceptions=False) as client,
        ):
            maker_token = _token(
                client,
                subject="maker:m3",
                roles=["asset-installer", "asset-install-approver"],
            )
            checker_token = _token(
                client,
                subject="checker:m3",
                roles=["asset-install-approver"],
            )
            command_keys = {
                "create": "m3-create-01",
                "submit": "m3-submit-02",
                "self_approve": "m3-self-approve-03",
                "stale_approve": "m3-stale-approve-04",
                "approve": "m3-approve-05",
                "apply": "m3-apply-06",
                "verify": "m3-verify-07",
                "rollback": "m3-rollback-08",
            }
            assert len(set(command_keys.values())) == len(command_keys)

            created_response = client.post(
                "/v1/bundle-installations",
                json={
                    "compositionId": lock.composition_id,
                    "lockRevision": lock.revision,
                    "overlayRevision": "overlay-m3",
                    "displayName": "M3 HTTP lifecycle",
                },
                headers=_headers(
                    maker_token,
                    **{"Idempotency-Key": command_keys["create"]},
                ),
            )
            created = _assert_installation_response(
                created_response,
                state="draft",
                revision=1,
            )
            installation_id = created["installationId"]
            action_path = f"/v1/bundle-installations/{installation_id}"

            submitted_response = client.post(
                f"{action_path}/submit",
                json={},
                headers=_headers(
                    maker_token,
                    **{
                        "Idempotency-Key": command_keys["submit"],
                        "If-Match": '"1"',
                    },
                ),
            )
            submitted = _assert_installation_response(
                submitted_response,
                state="submitted",
                revision=2,
            )
            approval = {
                "lockHash": submitted["current"]["lockHash"],
                "permissionDiffHash": submitted["current"]["permissionDiffHash"],
                "migrationPlanHash": submitted["current"]["migrationPlanHash"],
                "contributionDiffHash": submitted["current"]["contributionDiffHash"],
            }

            self_approval = client.post(
                f"{action_path}/approve",
                json=approval,
                headers=_headers(
                    maker_token,
                    **{
                        "Idempotency-Key": command_keys["self_approve"],
                        "If-Match": '"2"',
                    },
                ),
            )
            assert self_approval.status_code == 403
            assert self_approval.json()["code"] == "DUTY_SEPARATION_REQUIRED"

            stale_approval = client.post(
                f"{action_path}/approve",
                json=approval,
                headers=_headers(
                    checker_token,
                    **{
                        "Idempotency-Key": command_keys["stale_approve"],
                        "If-Match": '"1"',
                    },
                ),
            )
            assert stale_approval.status_code == 409
            assert stale_approval.json()["code"] == "REVISION_CONFLICT"

            still_submitted = client.get(
                action_path,
                headers=_headers(maker_token),
            )
            _assert_installation_response(
                still_submitted,
                state="submitted",
                revision=2,
            )

            approved_response = client.post(
                f"{action_path}/approve",
                json=approval,
                headers=_headers(
                    checker_token,
                    **{
                        "Idempotency-Key": command_keys["approve"],
                        "If-Match": '"2"',
                    },
                ),
            )
            approved = _assert_installation_response(
                approved_response,
                state="approved",
                revision=3,
            )
            assert approved["decision"]["actor"] == "checker:m3"
            assert approved["decision"]["submittedRevision"] == 2

            applied_response = client.post(
                f"{action_path}/apply",
                json={},
                headers=_headers(
                    maker_token,
                    **{
                        "Idempotency-Key": command_keys["apply"],
                        "If-Match": '"3"',
                    },
                ),
            )
            _assert_installation_response(
                applied_response,
                state="applied",
                revision=4,
            )

            active_response = client.post(
                f"{action_path}/verify",
                json={},
                headers=_headers(
                    maker_token,
                    **{
                        "Idempotency-Key": command_keys["verify"],
                        "If-Match": '"4"',
                    },
                ),
            )
            active = _assert_installation_response(
                active_response,
                state="active",
                revision=5,
            )
            assert active["activeRevision"] == 5
            assert active["previousActiveRevision"] is None

            rollback_response = client.post(
                f"{action_path}/rollback",
                json={"reason": "M3 verification rollback"},
                headers=_headers(
                    maker_token,
                    **{
                        "Idempotency-Key": command_keys["rollback"],
                        "If-Match": '"5"',
                    },
                ),
            )
            rolled_back = _assert_installation_response(
                rollback_response,
                state="rolled_back",
                revision=6,
            )
            assert rolled_back["activeRevision"] is None
            assert rolled_back["previousActiveRevision"] is None
            assert [event["toState"] for event in rolled_back["events"]] == [
                "draft",
                "submitted",
                "approved",
                "applied",
                "active",
                "rolled_back",
            ]
            assert [
                event["evidence"]["type"]
                for event in rolled_back["events"]
                if event["evidence"] is not None
            ] == ["dry_apply", "verification", "rollback"]

            fetched_response = client.get(
                action_path,
                headers=_headers(checker_token),
            )
            fetched = _assert_installation_response(
                fetched_response,
                state="rolled_back",
                revision=6,
            )
            assert fetched == rolled_back

            listed_response = client.get(
                "/v1/bundle-installations?state=rolled_back&limit=10&offset=0",
                headers=_headers(maker_token),
            )
            assert listed_response.status_code == 200
            listed = listed_response.json()
            assert listed["total"] == 1
            assert listed["items"] == [
                {
                    key: rolled_back[key]
                    for key in (
                        "installationId",
                        "displayName",
                        "state",
                        "currentRevision",
                        "activeRevision",
                        "previousActiveRevision",
                        "etagVersion",
                        "createdAt",
                        "updatedAt",
                    )
                }
            ]

            with scoped_connect() as conn:
                counts = conn.execute(
                    """
                    SELECT
                      (SELECT COUNT(*) FROM bundle_installation_command) AS commands,
                      (SELECT COUNT(*) FROM bundle_installation_revision) AS revisions,
                      (SELECT COUNT(*) FROM bundle_installation_event) AS events,
                      (SELECT COUNT(DISTINCT idempotency_key)
                         FROM bundle_installation_command) AS command_keys
                    """
                ).fetchone()
            assert counts == {
                "commands": 6,
                "revisions": 6,
                "events": 6,
                "command_keys": 6,
            }
