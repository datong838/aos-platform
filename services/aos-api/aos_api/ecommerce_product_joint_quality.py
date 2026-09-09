"""Fixed row-quality counts over verified observations; no business fact claim."""
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.configured_source_observation_evidence import ConfiguredObservationEvidenceStore
from aos_api.data_requirement_store import canonical_hash
from aos_api.ecommerce_business_investigation_case_selection import PostgresCanonicalShopSelectionSource
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.ecommerce_product_observation_comparison import _number
from aos_api.tenant_scope import TenantScope


# Immutable executable policy description; this is not an invented domain Owner.
_POLICY = (
    ("spec", "niushop.product-quality-observation/v1"),
    ("site", "1"),
    ("exclude", "strict-int is_delete=1 or goods_state=0; filter before dedup"),
    ("duplicates", "quarantine all candidate rows sharing a positive-int goods_id"),
    ("population", "distinct positive-int goods_id among eligible rows; unit=product"),
    ("identity", "positive-int goods_id and strict-int site_id=1"),
    ("title", "nonblank string"),
    ("availability", "strict-int goods_state=1 and is_delete=0"),
    ("category", "positive-int or canonical nonblank string other than 0; no foreign-key claim"),
    ("price", "finite nonnegative decimal; no boolean or default"),
    ("stock", "finite nonnegative integer decimal; no boolean or default"),
    ("createdAt", "strict positive-int Unix seconds <= read-finished time"),
    ("updatedAt", "strict positive-int Unix seconds <= read-finished time and >= valid createdAt"),
    ("joint", "all eight checks on the same eligible row"),
)
_RULE = ("niushop.product-public-row-quality", "1", "sha256:" + canonical_hash(dict(_POLICY)))
_FIELDS = ("identity", "title", "availability", "category", "price", "stock", "createdAt", "updatedAt")


@dataclass(frozen=True, slots=True)
class ProductJointQualityCounts:
    tenant: tuple[str, str]
    observation_ref: tuple[str, str, int, str]
    rule_version: tuple[str, str, str]
    measured_at: datetime
    observed_count: int
    excluded_count: int
    duplicate_count: int
    eligible_count: int
    distinct_population_count: int
    field_valid_counts: tuple[tuple[str, int], ...]
    joint_valid_count: int
    population_unit: str = "product"


def _positive_id(value):
    return type(value) is int and value > 0


def _strict(value, expected):
    return type(value) is int and value == expected


def _time(value, cutoff):
    return type(value) is int and 0 < value <= cutoff.timestamp()


def _counts(rows, finished_at):
    candidates = [row for row in rows if not (_strict(row.get("is_delete"), 1) or _strict(row.get("goods_state"), 0))]
    frequencies = Counter(row["goods_id"] for row in candidates if _positive_id(row.get("goods_id")))
    eligible = [row for row in candidates if not (_positive_id(row.get("goods_id")) and frequencies[row["goods_id"]] > 1)]
    counts = dict.fromkeys(_FIELDS, 0)
    joint = 0
    for row in eligible:
        category = row.get("category_id")
        created = _time(row.get("create_time"), finished_at)
        updated = _time(row.get("modify_time"), finished_at)
        checks = (
            _positive_id(row.get("goods_id")) and _strict(row.get("site_id"), 1),
            type(row.get("goods_name")) is str and bool(row["goods_name"].strip()),
            _strict(row.get("goods_state"), 1) and _strict(row.get("is_delete"), 0),
            _positive_id(category) or (type(category) is str and bool(category.strip()) and category == category.strip() and category != "0"),
            _number(row.get("price")) is not None,
            _number(row.get("goods_stock"), integer=True) is not None,
            created,
            created and updated and row["modify_time"] >= row["create_time"],
        )
        for field, valid in zip(_FIELDS, checks):
            counts[field] += int(valid)
        joint += int(all(checks))
    return (len(rows) - len(candidates), len(candidates) - len(eligible), len(eligible),
        len({row["goods_id"] for row in eligible if _positive_id(row.get("goods_id"))}), tuple(counts.items()), joint)


class ProductJointQualityReader:
    def __init__(self, transaction: HostTransaction, scope: TenantScope):
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError("joint quality requires HostTransaction and TenantScope")
        self._transaction, self._scope = transaction, scope

    def read(self, *, evidence_ref: InvestigationExactRef, rows, channel_ref, entity_ref, binding_ref):
        refs = (channel_ref, entity_ref, binding_ref)
        if any(type(ref) is not InvestigationExactRef or type(ref.revision) not in {int, str} for ref in refs):
            raise ValueError("exact selection references required")
        isolation = self._transaction.execute("SHOW transaction_isolation").fetchone()
        if isolation["transaction_isolation"] not in {"repeatable read", "serializable"}:
            raise ValueError("joint quality requires a stable transaction snapshot")
        saved = ConfiguredObservationEvidenceStore(self._transaction, self._scope).read_exact(evidence_ref)
        if saved is None:
            raise ValueError("quality observation unavailable")
        observation = saved.observation.observation
        if observation.spec_id != "niushop.product-quality-observation/v1" or observation.site_id != 1:
            raise ValueError("joint quality observation specification or site unsupported")
        saved.observation.verify_rows(rows)
        if any(not _strict(row.get("site_id"), 1) for row in rows):
            raise ValueError("joint quality row site drifted")
        bound = PostgresCanonicalShopSelectionSource(
            TransactionBoundConnectFactory(self._transaction, self._scope)).read_bound(self._scope)
        if (bound is None or bound.platform != "niushop" or bound.shop_or_marketplace_id != "1"
            or any(canonical_hash(ref.model_dump(mode="python", by_alias=True)) !=
                canonical_hash(actual.model_dump(mode="python", by_alias=True)) for ref, actual in zip(refs,
                (bound.selection.channel_ref, bound.selection.business_entity_ref, bound.selection.entity_channel_binding_ref)))):
            raise ValueError("joint quality shop selection drifted")
        excluded, duplicate, eligible, population, fields, joint = _counts(rows, observation.read_finished_at)
        now = self._transaction.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        if now < observation.read_finished_at:
            raise ValueError("joint quality measurement clock moved backwards")
        return ProductJointQualityCounts(self._scope.key,
            (evidence_ref.resource_type, evidence_ref.resource_id, evidence_ref.revision, evidence_ref.content_hash),
            _RULE, now, len(rows), excluded, duplicate, eligible, population, fields, joint)
