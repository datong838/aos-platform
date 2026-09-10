# A0-V 精确文本模型与路由权威实施方案

## 1. 目标与边界

为 `ProviderInstanceRevision:a0v-agnes-text-readonly-dev@1` 建立 A0-V 专用价格、`RegisteredModelRevision` 与单候选 `ModelRouteRevision`，通过生产 Eval Dataset/Suite/Run/Report/Gate 权威完成 exact 发布。退出标记固定为 `A0V_EXACT_TEXT_MODEL_ROUTE_AUTHORITY_GREEN`。

本切片不创建 CapabilityBinding、SkillBinding 或 AgentRun，不执行电商真实数据查询和业务 mutation，不使用 Prime OAuth，不执行 230 L0。Model/Route ready 只关闭 A0-V 静态运行前置，不代表 A1 首链成功。

## 2. 固定对象

- Price：`a0v-agnes-text-accounting-ceiling-v1@1`，CNY，input/output 均按每 1000 token 1 CNY 的保守内部记账上限；它不是供应商报价，A1 UsageReceipt 必须按实际账单或明确的内部零收费事实对账，不能用上限冒充实际费用。
- Model：`a0v-agnes-2-5-flash-readonly-dev@1`，Provider model `agnes-2.5-flash`，text→text，capabilities=`llm/chat/structured_output`，context window 按当前 quota 的 8000 token 保守限制。
- Route：`a0v-ecommerce-text-readonly-v1@1`，单模型、failover 策略但无 fallback 候选，绑定 `a0v-ecommerce-runtime-policy-v1@1`；task types 固定覆盖当前 10 个电商 capability ID 及 `analysis.summarize/chat.answer/content.generate`。
- Model 与 Route 都先用 placeholder gate 构造 evaluation candidate hash，Gate exact 指向该 candidate，再把 gate ref 写入最终 revision，沿用生产 Store 的 cycle-break 合同。

## 3. 模型评测

模型 Eval Suite 固定 8 个无客户数据 case：2 个 live positive case 验证不同中文指令下 HTTP/模型/非空响应/token metadata 合同，6 个 policy-contract case 验证 exact Provider、插件、network、data classification、Secret、单次尝试与无 fallback 边界。gate threshold=1.0，任一 case 不通过则不得发布 active Model。

两个 live case 各有独立 0600 attempt journal；Secret resolve、Provider/plugin/policy exact readback 均在 journal `submitted` 前完成。每 case 最多 1 次、timeout 10 秒、max output 32 token，禁止保存 prompt、answer、headers、Secret 或 response body。任一 submitted 后结果不明时不得重发。两次均成功后可根据结果 metadata 写一条新的 15 分钟 ProviderHealthObservation。

## 4. 路由评测

Route Suite 使用固定 SELECT/BLOCK 矩阵，覆盖允许 task+text+capability、未知 task、错误输入 modality、错误输出 modality、缺 capability；只执行候选路由合同判断，不调用 Provider。所有 case exact match 且 threshold=1.0 后才发布 active Route。

## 5. 执行顺序

1. 默认 preflight；apply 强制 `aos_meta_head`、正租户 exact authority 与 canary=0。
2. 在任何 DB mutation 和 Provider 调用前生成独立数据库备份。
3. 发布/回读非零 PriceSnapshot；为两个 live case 逐个执行 receipt-first journal 与单次探针。
4. 登记 model dataset/suite/run/report/gate，发布 active Model。
5. 登记 route dataset/suite/run/report/gate，发布 active Route。
6. 写健康观察，回读 Price/Model/Route/Gates/Health exact refs，验证 canary=0。
7. 重放必须 Provider call=0、DB mutation=0、所有 exact ref 不变；总依赖审计首门推进到 `capabilityProviderRoute`。

## 6. 停止条件与风险

任何价格币种/非零边界、Provider/策略/hash、Eval target、Gate freshness、模型响应、token metadata、journal、数据库身份或 canary 漂移均 fail closed。已提交调用出现 timeout/transport/未知状态时停止本切片，不切换 Provider、不重发。

保守内部计费上限会高估预算占用，安全但可能提前 hard-stop；A1 前必须明确实际计费来源。两条非空合同只能证明基础推理可用，不能证明电商分析质量；真实只读数据、来源引用、建议质量和完整业务闭环仍由 A1 两次首链验收。
