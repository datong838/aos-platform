# 栖月汇源与管道地图

## 受治理源

- Source ID：`niushop-qyh`
- Data OS 页面路由：`/data/sources/niushop-qyh`
- 连接器语义：MySQL SSH 隧道，只读访问远程 Niushop 库
- 作用域：必须由当前 Principal/TenantScope 回读，禁止把历史默认值当运行授权

Data FDE 可在 Data OS 内部进行 Schema/表/字段发现与最小采样。路径只用于接入工作，不得暴露给 Workshop 或转换为任意 SQL 工具。

## 已有 P01–P12

| Pipeline | 原始表 | ObjectType | Dataset RID |
|---|---|---|---|
| P01 | `ns_site` | Shop | `ri.aos.main.dataset.P01-shop-qyh` |
| P02 | `ns_goods` | Product | `ri.aos.main.dataset.P02-product-qyh` |
| P03 | `ns_goods_sku` | ProductSku | `ri.aos.main.dataset.P03-product-sku-qyh` |
| P04 | `ns_goods_category` | Category | `ri.aos.main.dataset.P04-category-qyh` |
| P05 | `ns_order` | Order | `ri.aos.main.dataset.P05-order-qyh` |
| P06 | `ns_order_goods` | OrderLine | `ri.aos.main.dataset.P06-order-line-qyh` |
| P07 | `ns_express_delivery_package` | Shipment | `ri.aos.main.dataset.P07-shipment-qyh` |
| P08 | `ns_member` | CustomerLite | `ri.aos.main.dataset.P08-customer-lite-qyh` |
| P09 | `ns_weapp` | Weapp | `ri.aos.main.dataset.P09-weapp-qyh` |
| P10 | `ns_config` | SystemConfig | `ri.aos.main.dataset.P10-system-config-qyh` |
| P11 | `ns_goods_evaluate` | ProductReview | `ri.aos.main.dataset.P11-product-review-qyh` |
| P12 | `ns_pay` | Payment | `ri.aos.main.dataset.P12-payment-qyh` |

先查已有 mapping 是否足以履行 DataNeed。远程库中发现的其他表只是 Source Evidence；未经 Profile、Mapping、质量和本体确认，不得直接上送 Workshop。

## 稳定源码位置

- Mapping：`bundles/platforms/ecommerce-niushop/content/mappings/p01-shop.yaml` 至 `p12-payment.yaml`
- DataSource Schema/Preview：`services/aos-api/aos_api/routers/phase6_schemas.py`
- Dataset 元数据：`GET /v1/datasets`，运行时必须按 Principal/TenantScope 过滤

路径是实现定位信息，不是当前运行成功证明；每次履行 DataNeed 都要回读 source mode、scope、revision、cutoff/watermark 和质量。
