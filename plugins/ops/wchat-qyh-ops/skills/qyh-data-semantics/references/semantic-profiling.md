# 语义剖析与水合流程

## 每个数据集的最小 Profile

- source、scope、schema revision、collectedAt、cutoff、watermark；
- grain、identity、tenant/site/weapp filters；
- 类型、单位、币种、时区、枚举与状态迁移；
- row count、缺失、唯一性、异常、时间连续性；
- PII/secret marking、retention、允许用途；
- 与页面、API、文件和其他表的对账结果。

## 源数据补证与投影对账

1. Workshop 先核对 P01–P12 Dataset、Object/Link、质量、cutoff/watermark 与页面证据。
2. 缺字段、缺对象或存在冲突时，生成 DataNeed；不得发出 SQL、Schema 或 Preview 调用。
3. Data OS 内部核对 `niushop-qyh` 原始来源、过滤条件、PII 排除、字段映射、增量策略和行数差异。
4. Data OS 返回 Dataset/DataProfile/MappingCandidate/Evidence；本体层完成身份解析与 Confirmed 投影。
5. 页面、Dataset 和本体投影冲突时，不覆盖任一方；保持 `CONFLICTED` 并等待补证。

## 关键防错

- 订单头和订单行不可混分母；
- 支付时间为空可能是未支付业务语义；
- 订单状态、支付状态、履约状态、退款状态必须分轴；
- 商品交易落点是 SKU；
- 店主资格、客户绑定、佣金流水是不同对象；
- 体验码是权益实例，不是普通优惠券；
- 未观察到不等于不存在，旧表存在不等于仍使用。

## 水合输出

`Dataset → DataProfile → MappingCandidate → Object/Link Candidate → identity/reconcile → CONFIRMED projection`。推断不得直接写 canonical Ontology。
