"""Complete protocol in disposable PG; fixture identities are not enterprise approval."""
import hashlib
import json
import os
import secrets
import shutil
from uuid import uuid4
from contextlib import contextmanager

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from aos_api.aip_bi_plan_issuer_connection import BIIssuerDatabaseConfig
from aos_api.aip_media_gate_source_reader import CompleteMediaGateSourceReader
from aos_api.aip_production_contract_store import (
    AipProductionContractStore, ProductionContractDependencyBlocked, canonical_hash,
)
from aos_api.aip_production_contracts import (
    RegisterMediaGateProfileRequest, RegisterReviewRuleRevisionRequest,
)
from aos_api.aip_source_issuer_connection import SourceIssuerDatabaseConfig, connect_source_issuer_write
from aos_api.tenant_scope import TenantScope
from tests.asset_registry import m5_bundle_support as bundles
from tests.asset_registry.test_qyh_installation_source_pg import installed  # noqa: F401

SCOPE = TenantScope("org-org", "dev-project")
ROLE = "aos_contract_source_issuer"


@pytest.fixture
def complete_case(tmp_path, monkeypatch, request):
    # The signing builder and authority readers remain original implementations.
    variant = getattr(request, "param", None)
    assert variant in (None, "ruleDigestMismatch", "testOnlyRule")
    root = tmp_path / "unsigned-inputs"
    shutil.copytree(bundles.M5_SOURCE_ROOT, root)
    gates = []
    bodies = []
    for kind in ("fact", "brand", "copyright", "platform"):
        body = RegisterReviewRuleRevisionRequest(
            ruleId="qyh-fixture-" + kind + ("-" + variant if variant else ""), revision=1,
            spec={"testOnly": variant == "testOnlyRule" and kind == "fact", "kind": kind, "fixtureOnly": True},
        )
        bodies.append(body)
        gates.append({"gateId": "media." + kind, "kind": kind, "returnStage": "review",
                      "ruleRef": {"resourceType": "EvalRuleRevision", "resourceId": body.rule_id,
                                  "revision": 1, "contentHash": canonical_hash(body.model_dump(mode="json", by_alias=True))}})
    if variant == "ruleDigestMismatch":
        gates[0]["ruleRef"]["contentHash"] = "d" * 64
    document = {"schema": "aos.ecommerce-media-gate-policy/v1", "policyId": "qyh-fixture-policy",
                "revision": 1, "profileId": "qyh-fixture-full-" + uuid4().hex, "profileRevision": 1, "gates": gates}
    artifact = root / "solutions/ecommerce-growth/content/media-gate-policies/full.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps(document))
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    monkeypatch.setattr(bundles, "M5_SOURCE_ROOT", root)
    runtime, _, schema = request.getfixturevalue("installed")

    @contextmanager
    def admin_factory(scope):
        with psycopg.connect(os.environ["AOS_DATABASE_URL"], row_factory=dict_row) as conn:
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", scope.key)
            yield conn

    original = AipProductionContractStore(admin_factory)
    for body in bodies:
        result = original.register_review_rule_revision(SCOPE, "fixture-rule-maker", body.rule_id, body)
        assert result.content_hash == canonical_hash(body.model_dump(mode="json", by_alias=True))
    bundle = runtime.prepared.by_id("solution.ecommerce.growth").signed
    material = runtime.registry_service.get_published_reference_material(
        publisher="aos", bundle_id=bundle.manifest.metadata.id, version=bundle.manifest.metadata.version,
    )
    coordinate = "aos/" + bundle.manifest.metadata.id + "@" + bundle.manifest.metadata.version
    body = RegisterMediaGateProfileRequest(
        profileId=document["profileId"], revision=1, gates=gates,
        sourceBundleRef={"resourceType": "BundleManifestRevision", "resourceId": coordinate,
                         "revision": material["publicationSequence"], "contentHash": material["contentHash"][7:]},
        signatureRef={"resourceType": "BundleSignatureVerification", "resourceId": coordinate,
                      "revision": material["publicationSequence"], "contentHash": material["signatureFingerprint"][7:]},
        policyRef={"resourceType": "MediaGatePolicyRevision", "resourceId": coordinate + "#" + document["policyId"],
                   "revision": 1, "contentHash": digest},
    )
    parts = conninfo_to_dict(os.environ["AOS_DATABASE_URL"])
    parent = tmp_path / "private"; parent.mkdir(mode=0o700)
    passfile = parent / "issuer.pgpass"
    password = secrets.token_hex(24)
    passfile.write_text(f"127.0.0.1:18431:{parts['dbname']}:{ROLE}:{password}\n")
    passfile.chmod(0o600)
    config = SourceIssuerDatabaseConfig("contract", BIIssuerDatabaseConfig("127.0.0.1", 18431, parts["dbname"], passfile))
    with psycopg.connect(os.environ["AOS_DATABASE_URL"], autocommit=True, row_factory=dict_row) as admin:
        assert admin.execute("SELECT count(*) AS n FROM pg_roles WHERE rolname=%s", (ROLE,)).fetchone()["n"] == 0
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {}").format(sql.Identifier(ROLE), sql.Literal(password)))
        try:
            admin.execute(sql.SQL("GRANT USAGE ON SCHEMA {},public TO {}").format(sql.Identifier(schema), sql.Identifier(ROLE)))
            admin.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {}").format(sql.Identifier(schema), sql.Identifier(ROLE)))
            for table in ("aip_review_rule_revision", "aip_media_gate_profile_revision", "aip_production_contract_receipt"):
                admin.execute(sql.SQL("GRANT SELECT,INSERT ON public.{} TO {}").format(sql.Identifier(table), sql.Identifier(ROLE)))
                admin.execute(sql.SQL("CREATE POLICY qyh_fixture_issuer ON public.{} TO {} USING (org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK (org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(sql.Identifier(table), sql.Identifier(ROLE)))
            for table in ("aip_responsibility_plan_head", "aip_responsibility_plan_revision", "aip_production_contract_receipt", "aip_review_rule_revision"):
                admin.execute(sql.SQL("REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON public.{} FROM aos_runtime").format(sql.Identifier(table)))

            @contextmanager
            def factory(scope):
                with connect_source_issuer_write(config, scope) as conn:
                    conn.execute(sql.SQL("SET search_path TO {},public").format(sql.Identifier(schema)))
                    yield conn

            reader = CompleteMediaGateSourceReader(loader=runtime.prepared.loader)
            store = AipProductionContractStore(contract_connect_factory=factory, media_gate_source_resolver=reader)
            yield store, factory, reader, body, admin, runtime
        finally:
            # Only this fixture-created role has ownership, and only in this database.
            admin.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(ROLE)))
            admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(ROLE)))
            passfile.unlink()


def test_complete_original_issuer_registration_commits_and_replays(complete_case):
    store, factory, reader, body, admin, _ = complete_case
    with factory(SCOPE) as conn:
        before = conn.execute("SELECT txid_current() AS id").fetchone()["id"]
        assert reader(conn, SCOPE, body) is True
        assert conn.execute("SELECT txid_current() AS id").fetchone()["id"] == before
    result = store.register_media_gate_profile(SCOPE, "fixture-source-maker", "complete-positive", body)
    replay = store.register_media_gate_profile(SCOPE, "fixture-source-maker", "complete-positive", body)
    assert result == replay
    row = admin.execute("SELECT count(*) AS n FROM public.aip_production_contract_receipt WHERE operation='media_gate_profile.register' AND idempotency_key='complete-positive'").fetchone()
    assert row["n"] == 1


@pytest.mark.parametrize("change", ["tenant", "policyHash", "gateRuleRefDrift", "publicationRevoked", "runtimeSourceWrite", "missingReceiptVisibility"])
def test_complete_original_source_rejects_without_profile_receipt(complete_case, change):
    store, factory, reader, body, admin, runtime = complete_case
    with factory(SCOPE) as conn:
        assert reader(conn, SCOPE, body) is True
    count_sql = "SELECT (SELECT count(*) FROM public.aip_media_gate_profile_revision) AS profiles, (SELECT count(*) FROM public.aip_production_contract_receipt WHERE operation='media_gate_profile.register') AS receipts"
    before = admin.execute(count_sql).fetchone()
    scope = SCOPE
    if change == "tenant":
        scope = TenantScope("dev-org", "dev-project")
    elif change == "policyHash":
        body = body.model_copy(update={"policy_ref": body.policy_ref.model_copy(update={"content_hash": "d" * 64})})
    elif change == "gateRuleRefDrift":
        body = body.model_copy(update={"gates": [body.gates[0].model_copy(update={"rule_ref": body.gates[0].rule_ref.model_copy(update={"content_hash": "d" * 64})}), *body.gates[1:]]})
    elif change == "publicationRevoked":
        bundle = runtime.prepared.by_id("solution.ecommerce.growth").signed
        runtime.registry_service.revoke(
            publisher="aos", bundle_id=bundle.manifest.metadata.id, version=bundle.manifest.metadata.version,
            actor="fixture-publisher", roles={"asset-publisher"}, publisher_scopes={"aos"},
            reason="isolated complete source negative",
        )
    elif change == "runtimeSourceWrite":
        admin.execute("GRANT INSERT ON public.aip_production_contract_receipt TO aos_runtime")
    else:
        # Retain immutable actual receipts; removing their visibility must not
        # allow the issuer to treat Rule rows alone as registration provenance.
        admin.execute("ALTER POLICY qyh_fixture_issuer ON public.aip_production_contract_receipt USING (org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true) AND operation<>'review_rule.register')")
    with pytest.raises(ProductionContractDependencyBlocked):
        store.register_media_gate_profile(scope, "fixture-source-maker", "complete-negative", body)
    assert admin.execute(count_sql).fetchone() == before
