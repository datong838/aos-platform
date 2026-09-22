# 跨层数据边界与 DataNeed

## 架构军规

`wchat-qyh-ops` 属于工作台/经营操作域。它不得访问 MySQL、SSH 隧道、数据源 Schema、原始表、Connector Preview 或任意 SQL 接口。

正确链路：

```text
Workshop 经营问题 / DataNeed
  → Handoff 给 qyh-data-onboarding（Data OS/FDE 身份）
  → Data OS/Connector 内部访问 niushop-qyh
  → Landing/Profile/Quality/Lineage/Dataset
  → Data Semantics MappingCandidate
  → Ontology identity/reconcile/Confirmed Object & Link
  → AIP 分析与方案
  → Workshop 只读消费与受控决策
```

## 工作台可消费的数据产品

| Pipeline | ObjectType | Dataset RID 模式 |
|---|---|---|
| P01 | Shop | `ri.aos.main.dataset.P01-shop-qyh` |
| P02 | Product | `ri.aos.main.dataset.P02-product-qyh` |
| P03 | ProductSku | `ri.aos.main.dataset.P03-product-sku-qyh` |
| P04 | Category | `ri.aos.main.dataset.P04-category-qyh` |
| P05 | Order | `ri.aos.main.dataset.P05-order-qyh` |
| P06 | OrderLine | `ri.aos.main.dataset.P06-order-line-qyh` |
| P07 | Shipment | `ri.aos.main.dataset.P07-shipment-qyh` |
| P08 | CustomerLite | `ri.aos.main.dataset.P08-customer-lite-qyh` |
| P09 | Weapp | `ri.aos.main.dataset.P09-weapp-qyh` |
| P10 | SystemConfig | `ri.aos.main.dataset.P10-system-config-qyh` |
| P11 | ProductReview | `ri.aos.main.dataset.P11-product-review-qyh` |
| P12 | Payment | `ri.aos.main.dataset.P12-payment-qyh` |

工作台只能经正式、租户隔离的查询契约读取这些数据产品或相应 Confirmed Object/Link。数量、行数、同步状态和“在线”标记必须现场回读。

## DataNeed 最小契约

当经营分析缺少数据时，工作台提交：

- `purpose`：要回答的经营问题；
- `scope`：org/workspace、店铺、平台和时间范围；
- `requiredSemantics`：所需对象、关系、指标或状态语义；
- `currentEvidenceRefs`：已有 Dataset/Object/Page Evidence；
- `gap`：缺字段、缺对象、口径冲突、新鲜度不足或质量失败；
- `minimumFields`：满足问题所需的最小字段，不提供 SQL；
- `piiPolicy`、retention、deadline 和 priority；
- `acceptance`：期待返回的 Dataset/Profile/Mapping/Evidence 及质量门。

DataNeed 只表达需求，不携带 SSH/MySQL 凭据、连接参数、表扫描指令或原始客户明细。

DataNeed 的默认接收者是 `qyh-data-onboarding`，但只有持有 Data OS/FDE capability binding 的运行身份可以执行。Workshop 只持有 Handoff/状态/Receipt 引用。

## 返回契约

Data OS/本体层返回：

- Dataset exact ref、revision、cutoff/watermark；
- DataProfile 与质量结论；
- MappingCandidate 或 Confirmed mapping；
- Object/Link exact refs 与 identity/reconcile 状态；
- lineage、Evidence、PII marking 和 nonClaims；
- blocked/unknown 原因。

在返回对象未 Confirmed、质量不合格或 scope 不一致时，工作台保持 blocked，不得自行回钻源库或以页面截图替代数据产品。

## 写操作边界

本体数据和工作台投影均不是外部写通道。上架、下架、改价、发券等动作必须经明确授权的浏览器技能或正式 Proposal → Approval → Lease → Adapter → Receipt → Reconcile 链执行，并在动作后回读权威页面。
