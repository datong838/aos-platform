"""Fixed public-field comparison; no business-fact or fulfillment authority."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import re

from aos_api.aip_contracts import ResourceRef
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.configured_source_observation_evidence import ConfiguredObservationEvidenceStore
from aos_api.ecom_core_models import deterministic_hash
from aos_api.ecommerce_canonical_population import CanonicalPopulationReader
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.ecommerce_business_investigation_case_selection import PostgresCanonicalShopSelectionSource
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True, slots=True)
class ProductObservationComparison:
    observation_evidence_ref: InvestigationExactRef
    canonical_refs: tuple[ResourceRef, ...]
    source_count: int
    canonical_count: int
    common_count: int
    only_source_count: int
    only_canonical_count: int
    match_counts: tuple[tuple[str, int], ...]
    invalid_counts: tuple[tuple[str, int], ...]
    mismatch_counts: tuple[tuple[str, int], ...]


def _number(value, *, integer=False):
    if type(value) not in {str, int, float, Decimal}:
        return None
    if type(value) is str and (not value or value.strip() != value):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite() or number < 0 or (integer and number != number.to_integral_value()):
        return None
    return number


class ProductObservationComparisonReader:
    def __init__(self, transaction: HostTransaction, scope: TenantScope):
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError("product comparison requires HostTransaction and TenantScope")
        self._transaction, self._scope = transaction, scope

    def compare(self, *, evidence_ref, rows, channel_ref, entity_ref, binding_ref):
        saved = ConfiguredObservationEvidenceStore(self._transaction,self._scope).read_exact(evidence_ref)
        if saved is None:
            raise ValueError("configured observation unavailable")
        saved.observation.verify_rows(rows)
        observation = saved.observation.observation
        if observation.spec_id != "niushop.product-observation/v1":
            raise ValueError("product comparison observation specification unsupported")
        bound = PostgresCanonicalShopSelectionSource(
            TransactionBoundConnectFactory(self._transaction,self._scope)).read_bound(self._scope)
        if (observation.site_id != 1 or bound is None or bound.platform != "niushop"
            or bound.shop_or_marketplace_id != "1"):
            raise ValueError("product observation shop binding unavailable")
        source = {}
        for row in rows:
            identity = row.get("goods_id")
            if (type(identity) is not int or identity <= 0 or type(row.get("site_id")) is not int
                or row["site_id"] != observation.site_id or identity in source):
                raise ValueError("ambiguous product observation identity or scope")
            source[identity] = row
        population = CanonicalPopulationReader(self._transaction,self._scope).read(
            channel_ref=channel_ref,entity_ref=entity_ref,binding_ref=binding_ref,object_types=("Product",))
        canonical = {}
        for ref in population.sources:
            identity = json.loads(ref.resource_id.removeprefix("ecom/v1:"))
            if (identity[:5] != [*self._scope.key,"niushop",str(observation.site_id),"Product"]
                or re.fullmatch(r"niushop:1:[1-9][0-9]*",identity[5]) is None):
                raise ValueError("canonical product identity or shop scope drifted")
            row = self._transaction.execute("""SELECT * FROM public.ecom_object
                WHERE org_id=%s AND workspace_id=%s AND platform=%s AND shop_or_marketplace_id=%s
                  AND object_type=%s AND external_id=%s AND payload_hash=%s
                  AND canonical_status='active' AND deleted_at IS NULL""",
                (*identity,ref.revision)).fetchone()
            if row is None:
                raise ValueError("canonical product revision unavailable")
            actual_identity = {key:row[key] for key in (
                "org_id","workspace_id","platform","shop_or_marketplace_id","external_id")}
            payload = dict(identity=actual_identity,objectType=row["object_type"],
                sourceUpdatedAt=row["source_updated_at"],sourceTimezone=row["source_timezone"],
                status={"canonical_value":row["canonical_status"],"raw_status":row["raw_status"],"unknown":False},
                isDeleted=row["deleted_at"] is not None,schemaVersion=row["schema_version"],properties=row["properties"])
            if (deterministic_hash(payload) != ref.revision or row["payload_hash"] != ref.revision
                or type(row["properties"]) is not dict):
                raise ValueError("canonical product payload hash drifted")
            canonical[int(identity[5].removeprefix("niushop:1:"))] = row["properties"]
        common = source.keys() & canonical.keys()
        counts = dict(title=0,price=0,stock=0)
        invalid = dict(title=0,price=0,stock=0)
        for identity in common:
            left,right = source[identity],canonical[identity]
            title = left.get("goods_name")
            if (type(title) is not str or not title.strip()
                or type(right.get("title")) is not str or not right["title"].strip()):
                invalid["title"] += 1
            elif title == right["title"]:
                counts["title"] += 1
            for field,source_field in (("price","price"),("stock","goods_stock")):
                a = _number(left.get(source_field),integer=field=="stock")
                b = _number(right.get(field),integer=field=="stock")
                if a is None or b is None:
                    invalid[field] += 1
                elif a == b:
                    counts[field] += 1
        return ProductObservationComparison(evidence_ref,population.sources,len(source),len(canonical),
            len(common),len(source.keys()-canonical.keys()),len(canonical.keys()-source.keys()),tuple(counts.items()),tuple(invalid.items()),
            tuple((field,len(common)-counts[field]-invalid[field]) for field in counts))
