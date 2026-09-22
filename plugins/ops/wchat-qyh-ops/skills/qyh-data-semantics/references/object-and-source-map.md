# 栖月汇对象与来源地图

## 三层数据身份与访问权

- 原始来源：AOS Source `niushop-qyh`，连接器为 MySQL SSH 隧道；仅 Data OS/Connector 内部可访问。
- 治理数据集：`ri.aos.main.dataset.Pxx-...-qyh`；由映射管道生成，带 scope、状态、cutoff/watermark 和质量上下文；Workshop 只读引用。
- 本体对象/关系：由 Dataset 映射形成的 Confirmed Object/Link 投影；它是工作台主要事实面，不是源表副本。

先用本体对象/关系和治理数据集回答经营问题；遇到字段缺失、长尾表或语义冲突，提交 DataNeed，由 Data OS 回钻原始来源并返回新的 Dataset/Profile/Mapping/Evidence。Workshop 不接收源表访问权。

| 经营对象 | 主要结构化来源 | 关键关系 |
|---|---|---|
| Site / Weapp | site, weapp, config | 店铺和端范围 |
| Member | member, member_weapp, member_account | 等级、资产、分享者/来源、店主资格 |
| Goods / SKU | goods, goods_sku, goods_weapp, category | SPU—SKU—端可见—引流品 |
| Order / OrderLine | order, order_goods, order_log | 买家、商品、状态和金额 |
| Payment / Refund | pay, pay_refund, order_refund_log | 订单支付与逆向 |
| Fulfillment | store, package, verify, local | 配送、自提、核销 |
| ShareExperience | member_shop_share_experience, goods_share_lead | 母单—权益实例—体验子单 |
| Commission | member_shop_commission_log/config/line | 订单—买家—推广者—结算/逆转 |
| Content | article, help, notice, media | 知识—商品—行为候选 |
| Coupon/Promotion | promotion_* / coupon / order refs | 活动—领取—使用—订单 |

横切身份：`site_id`、`weapp_id`、`member_id`、`order_id`、`goods_id`、`sku_id`。Niushop 多为逻辑外键，必须做孤儿与范围检查。

参考方案：`docs/palantier/20_tech/电商平台接入/微商城电商接入方案/niushop-数据表与核心对象关系.md`。旧数量和运行状态需现场复核。
