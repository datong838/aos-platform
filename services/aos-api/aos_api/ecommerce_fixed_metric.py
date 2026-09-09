"""Transaction-bound fixed metric definitions in the existing public Owner."""
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
from aos_api.aip_eval_contracts import MetricDefinitionRevision
from aos_api.data_requirement_store import canonical_hash
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.tenant_scope import TenantScope


def fixed_metric(transaction: HostTransaction, scope: TenantScope,
                 expected: MetricDefinitionRevision, *, actor: str, ensure=False):
    if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
        raise TypeError("fixed metric requires HostTransaction and TenantScope")
    body = expected.model_dump(mode="json", by_alias=True)
    if (type(expected.revision) is not int or expected.content_hash !=
            canonical_hash({key: value for key, value in body.items() if key != "contentHash"})):
        raise ValueError("fixed metric definition hash invalid")
    row = transaction.execute("""SELECT * FROM public.aip_metric_definition_revision
        WHERE org_id=%s AND project_id=%s AND metric_id=%s AND revision=%s""",
        (*scope.key, expected.metric_id, expected.revision)).fetchone()
    if row is None and ensure:
        owner = AipEvalAuthorityStore(TransactionBoundConnectFactory(transaction, scope))
        owner._append_contract(scope, table="public.aip_metric_definition_revision",
            id_column="metric_id", identifier=expected.metric_id,
            columns=("metric_id", "revision", "content_hash", "definition", "actor"),
            values=(expected.metric_id, expected.revision, expected.content_hash, owner._json(expected), actor),
            expected=expected, parser=lambda row: MetricDefinitionRevision.model_validate(row["definition"]),
            extra_lookup=("revision", expected.revision))
        return fixed_metric(transaction, scope, expected, actor=actor)
    if row is None:
        raise ValueError("fixed metric unavailable")
    if (canonical_hash(row["definition"]) != canonical_hash(body) or row["definition"] != body
        or row["content_hash"] != expected.content_hash or row["metric_id"] != expected.metric_id
        or type(row["revision"]) is not int or row["revision"] != expected.revision
        or (row["org_id"], row["project_id"]) != scope.key):
        raise ValueError("fixed metric drifted")
    return ResourceRef(resource_type="MetricDefinitionRevision", resource_id=expected.metric_id,
        revision=str(expected.revision), authority="postgres:aip_metric_definition_revision")
