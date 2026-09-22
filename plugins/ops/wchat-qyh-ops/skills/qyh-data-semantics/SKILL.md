---
name: qyh-data-semantics
description: Consume authorized 栖月汇 AOS P01-P12 datasets and confirmed Ontology projections, map admin pages, mini-program journeys, files, and owner explanations into evidence-backed business objects, links, and metrics, and raise governed DataNeed requests when source coverage is insufficient. Use for governed datasets, state dictionaries, joins, freshness, schema reasoning results, adaptive profiling outputs, customer/order/product/experience/commission relationships, and cross-source reconciliation. Never use this Workshop skill to access MySQL, SSH tunnels, connector schemas, or raw source previews.
---

# 栖月汇数据语义

先读 [跨层数据边界与 DataNeed](references/aos-data-boundary-and-request.md)、[对象关系地图](references/object-and-source-map.md) 和 [语义剖析流程](references/semantic-profiling.md)。

## 铁律

> 先确定业务粒度、身份、状态和时间语义，再算指标；页面同名、字段同名和表存在都不等于语义相同。

## 多源优先级

- 跨表经营分析与本体关系：只读 AOS P01–P12 数据集和 Confirmed 对象/关系投影，必须携带 dataset、mapping、cutoff/watermark 和质量上下文；
- 未映射事实、源字段、全库发现和源状态核对：提交 DataNeed 给 Data OS；Workshop 不访问 `niushop-qyh` Source、Connector Schema 或 Preview；
- 配置与运营流程：管理后台；
- 消费者可见旅程：微信小程序；
- 商业规则与线下成本：负责人说明，标记 `OWNER_EXPLANATION`；
- 冲突：保留两个来源并进入 reconcile，不覆盖。

## 工作流

1. 明确 purpose、scope、时间窗和最小字段。
2. 选择证据层：AOS 数据集/本体投影、页面或多面核验；不得访问原始库。
3. 识别表/数据集/页面粒度、主键/自然键、site/weapp/tenant 范围。
4. 建立状态字典、币种/单位、事件时间、处理时间和 cutoff。
5. 做缺失、基数、唯一性、分布、连续性和跨源对账。
6. 形成 DataProfile 与 Object/Link/Metric 映射候选。
7. `CONFIRMED` 才进入受控投影；新语义保持 `CANDIDATE`，冲突保持 `CONFLICTED/UNKNOWN`。

## 隐私

客户分析优先使用脱敏键和聚合。默认不采集手机号、地址、openid、头像、昵称、支付号和完整订单明细。Workshop 不接收 SSH、数据库地址、账号、密码、密钥、SQL 或连接参数；这些只能由 Data OS/Connector 内部安全解析。禁止绕过 Data OS 读取或写入远程 MySQL。
