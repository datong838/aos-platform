"""Fixed internal-content candidates from a complete observed product population.

This calculation is neither a sales ranking nor fulfillment/Insight authority.
The existing observation cap remains enforced; there is no silent truncation.
"""
from copy import deepcopy
from dataclasses import dataclass

from aos_api.configured_source_observation_evidence import ConfiguredObservationEvidenceStore
from aos_api.ecommerce_product_joint_quality import (
    ProductJointQualityCounts, ProductJointQualityReader, _eligible_rows, product_row_checks,
)
from aos_api.ecommerce_product_observation_comparison import _number
from aos_api.source_read_observation import observed_rows_hash


@dataclass(frozen=True, slots=True)
class ProductContentCandidate:
    product_id: int
    title: str
    stock: int
    observed_row_hash: str


@dataclass(frozen=True, slots=True)
class ProductContentSnapshot:
    quality: ProductJointQualityCounts
    preparable_product_count: int
    candidates: tuple[ProductContentCandidate, ...]
    selection_policy: str = 'stock-desc-goods-id-asc-first-five/v1'
    limitations: tuple[str, ...] = (
        '内部商品介绍准备候选，不是销量排名或收益预测',
        '库存排序不证明市场需求；价格文案还需要正式币种来源',
        '质量计数不证明上游新鲜度或完整经营指标ready',
    )


class ProductContentSnapshotReader:
    def __init__(self, transaction, scope):
        self._quality = ProductJointQualityReader(transaction, scope)
        self._observations = ConfiguredObservationEvidenceStore(transaction, scope)

    def read(self, *, evidence_ref, rows, channel_ref, entity_ref, binding_ref):
        values=deepcopy(dict(evidence_ref=evidence_ref,rows=rows,channel_ref=channel_ref,entity_ref=entity_ref,binding_ref=binding_ref))
        quality=self._quality.read(**values)
        saved=self._observations.read_exact(values['evidence_ref'])
        if saved is None:
            raise ValueError('configured product observation unavailable')
        _,_,eligible=_eligible_rows(values['rows'])
        qualified=[row for row in eligible if all(product_row_checks(row,saved.observation.observation.read_finished_at))]
        if len(qualified)!=quality.joint_valid_count:
            raise ValueError('product content and quality rules drifted')
        candidates=[]
        for row in qualified:
            stock=_number(row['goods_stock'],integer=True)
            if stock>9_223_372_036_854_775_807:
                raise ValueError('product content stock exceeds supported integer range')
            if stock==0:
                continue
            if len(row['goods_name'])>4000:
                raise ValueError('complete product title exceeds supported length')
            candidates.append(ProductContentCandidate(product_id=row['goods_id'],title=row['goods_name'],stock=int(stock),observed_row_hash=observed_rows_hash([row])))
        candidates.sort(key=lambda item:(-item.stock,item.product_id))
        return ProductContentSnapshot(quality=quality,preparable_product_count=len(candidates),candidates=tuple(candidates[:5]))
