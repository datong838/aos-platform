"""At-most-once BI issuer orchestration; these doubles are not formal DB acceptance."""

from datetime import datetime, timezone

from aos_api.auth import Principal
from aos_api.aip_bi_plan_issuer_contracts import BIIssuerPrepareCommand, BIIssuerRebindCommand
from aos_api.aip_production_contract_store import (
    SignedBIOriginalInstallationBinding, SignedBIPlanReceiptReadback,
    SignedBIPlanRebindReceiptBinding, SignedBIPlanRebindReceiptReadback,
    ProductionContractNotFound,
)
from aos_api.aip_production_contracts import ExactRevisionRef


INSTALLATION = "42785d78-5914-4a54-a078-e5d2c7f48481"
ACTOR = Principal(subject="checker", org_id="org-org", project_id="dev-project", token_kind="oidc")


def _command(kind="prepare"):
    raw = dict(schemaVersion=1, bearerToken="header.payload.signature",
               orgId="org-org", projectId="dev-project", installationId=INSTALLATION,
               expectedETagVersion=3 if kind == "prepare" else 4,
               idempotencyKey="bi-prepare-1" if kind == "prepare" else "bi-rebind-1")
    if kind == "prepare":
        return BIIssuerPrepareCommand.model_validate(raw)
    raw.update(planId="plan-1", prepareIdempotencyKey="bi-prepare-1",
               expectedPlanVersion=1)
    return BIIssuerRebindCommand.model_validate(raw)


def _ref(kind="ResponsibilityPlanRevision", revision=1):
    return ExactRevisionRef(resource_type=kind, resource_id="plan-1" if kind.startswith("ResponsibilityPlan") else "template-1",
                            revision=revision, content_hash="a" * 64)


def _prepare_receipt(etag=3):
    return SignedBIPlanReceiptReadback(
        receipt_id="receipt-prepare-1", request_hash="b" * 64,
        result_ref=_ref(), created_at=datetime.now(timezone.utc),
        installation_binding=SignedBIOriginalInstallationBinding(
            installation_id=INSTALLATION, installation_etag=etag,
            template_ref=_ref("ResponsibilityTemplateRevision"), actor="checker"),
        installation_binding_verified=True, plan_revision_verified=True)


def _rebind_receipt(prepare_receipt_id="receipt-prepare-1"):
    return SignedBIPlanRebindReceiptReadback(
        receipt_id="receipt-rebind-1", request_hash="c" * 64,
        result_ref=_ref(revision=2), created_at=datetime.now(timezone.utc),
        rebind_binding=SignedBIPlanRebindReceiptBinding(
            installation_id=INSTALLATION, installation_etag=4,
            prepare_receipt_id=prepare_receipt_id,
            approved_template_ref=_ref("ResponsibilityTemplateRevision"),
            active_template_ref=_ref("ResponsibilityTemplateRevision", revision=2),
            actor="checker"),
        original_preparation_verified=True, plan_revision_verified=True)


class _PrepareService:
    calls = 0
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = 0
    def prepare(self, *args, **kwargs):
        self.calls += 1
        assert args[0].key == ("org-org", "dev-project")
        assert kwargs["principal"].subject == "checker"
        if self.fail:
            raise ConnectionError("commit outcome unknown")


class _RebindService:
    def __init__(self): self.calls = 0
    def rebind(self, *args, **kwargs):
        self.calls += 1
        assert kwargs["prepare_key"] == "bi-prepare-1"


class _Reader:
    def __init__(self, receipt=None):
        self.receipt = receipt
        self.calls = 0
    def read(self, *args, **kwargs):
        self.calls += 1
        assert kwargs["principal"].subject == "checker"
        if self.receipt is None:
            raise ProductionContractNotFound("not found")
        return self.receipt


def _dispatch(command, directory, service, prep_reader, rebind_reader=None, rebind_service=None):
    from aos_api.aip_bi_plan_issuer_service import dispatch_bi_issuer_command
    return dispatch_bi_issuer_command(
        command, attempt_directory=directory,
        prepare_service=service, rebind_service=rebind_service or _RebindService(),
        prepare_receipt_reader=prep_reader,
        rebind_receipt_reader=rebind_reader or _Reader())


def test_prepare_reserves_once_and_repeat_only_reads_receipt(monkeypatch, tmp_path):
    from aos_api import aip_bi_plan_issuer_service as module
    calls = []
    monkeypatch.setattr(module, "authenticate_bi_issuer_request", lambda _: (calls.append(1) or ACTOR))
    directory = tmp_path / "attempts"; directory.mkdir(mode=0o700)
    service, reader = _PrepareService(), _Reader(_prepare_receipt())
    command = _command()
    first = _dispatch(command, directory, service, reader)
    second = _dispatch(command, directory, service, reader)
    assert [first.status, second.status] == ["observed", "observed"]
    assert first.receipt.receipt_id == "receipt-prepare-1"
    assert service.calls == 1 and reader.calls == 2 and len(calls) == 2
    markers = list(directory.glob("*.json"))
    assert len(markers) == 1 and "header.payload.signature" not in markers[0].read_text()


def test_unknown_commit_is_read_only_reconciled_never_resent(monkeypatch, tmp_path):
    from aos_api import aip_bi_plan_issuer_service as module
    monkeypatch.setattr(module, "authenticate_bi_issuer_request", lambda _: ACTOR)
    directory = tmp_path / "attempts"; directory.mkdir(mode=0o700)
    service, reader = _PrepareService(fail=True), _Reader()
    command = _command()
    assert _dispatch(command, directory, service, reader).status == "unresolved"
    reader.receipt = _prepare_receipt()
    assert _dispatch(command, directory, service, reader).status == "observed"
    assert service.calls == 1 and reader.calls == 2


def test_conflicting_command_or_receipt_never_dispatches_again(monkeypatch, tmp_path):
    from aos_api import aip_bi_plan_issuer_service as module
    monkeypatch.setattr(module, "authenticate_bi_issuer_request", lambda _: ACTOR)
    directory = tmp_path / "attempts"; directory.mkdir(mode=0o700)
    service, reader = _PrepareService(), _Reader(_prepare_receipt(etag=2))
    assert _dispatch(_command(), directory, service, reader).status == "conflict"
    changed = _command().model_copy(update={"expected_etag_version": 5})
    assert _dispatch(changed, directory, service, reader).status == "conflict"
    assert service.calls == 1


def test_changed_verified_actor_cannot_reuse_prior_attempt(monkeypatch, tmp_path):
    from aos_api import aip_bi_plan_issuer_service as module
    actor = [ACTOR]
    monkeypatch.setattr(module, "authenticate_bi_issuer_request", lambda _: actor[0])
    directory = tmp_path / "attempts"; directory.mkdir(mode=0o700)
    service, reader = _PrepareService(), _Reader(_prepare_receipt())
    assert _dispatch(_command(), directory, service, reader).status == "observed"
    actor[0] = Principal(subject="another", org_id="org-org",
                         project_id="dev-project", token_kind="oidc")
    assert _dispatch(_command(), directory, service, reader).status == "conflict"
    assert service.calls == 1 and reader.calls == 1


def test_rebind_requires_matching_original_receipt(monkeypatch, tmp_path):
    from aos_api import aip_bi_plan_issuer_service as module
    monkeypatch.setattr(module, "authenticate_bi_issuer_request", lambda _: ACTOR)
    directory = tmp_path / "attempts"; directory.mkdir(mode=0o700)
    service, prep, rebind = _RebindService(), _Reader(_prepare_receipt()), _Reader(_rebind_receipt())
    result = _dispatch(_command("rebind"), directory, _PrepareService(), prep, rebind, service)
    assert result.status == "observed" and service.calls == 1
    assert rebind.calls == 1 and prep.calls == 1
    wrong = _Reader(_rebind_receipt("other-receipt"))
    assert _dispatch(_command("rebind"), directory, _PrepareService(), prep, wrong, service).status == "conflict"
    assert service.calls == 1


def test_untrusted_attempt_directory_fails_before_write(monkeypatch, tmp_path):
    from aos_api import aip_bi_plan_issuer_service as module
    monkeypatch.setattr(module, "authenticate_bi_issuer_request", lambda _: ACTOR)
    directory = tmp_path / "attempts"; directory.mkdir(mode=0o755)
    service = _PrepareService()
    assert _dispatch(_command(), directory, service, _Reader()).status == "unresolved"
    assert service.calls == 0
