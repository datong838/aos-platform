# A0-V 精确文本模型与路由权威实施方案

## 1. 目标与边界

为 `ProviderInstanceRevision:a0v-agnes-text-readonly-dev@1` 建立 A0-V 专用价格、`RegisteredModelRevision` 与单候选 `ModelRouteRevision`，通过生产 Eval Dataset/Suite/Run/Report/Gate 权威完成 exact 发布。退出标记固定为 `A0V_EXACT_TEXT_MODEL_ROUTE_AUTHORITY_GREEN`。

本切片不创建 CapabilityBinding、SkillBinding 或 AgentRun，不执行电商真实数据查询和业务 mutation，不使用 Prime OAuth，不执行 230 L0。Model/Route ready 只关闭 A0-V 静态运行前置，不代表 A1 首链成功。

## 2. 固定对象

- Price：待取得当前 Provider/model 对应的可核实计费来源、币种、输入输出单位和有效期后建立。撤销每 1000 token 1 CNY 的虚构上限方案；预算上限不能作为单价。缺少真实价格时保持 PRICE_AUTHORITY_UNAVAILABLE，不发布 active Model/Route，也不将 unknown 记为零。
- Model：`a0v-agnes-2-5-flash-readonly-dev@1`，Provider model `agnes-2.5-flash`，text→text，capabilities 初始候选仅为 `llm/chat`；`structured_output` 必须另有结构化响应合同及真实评测证明，context window 按当前 quota 的 8000 token 保守限制。
- Route：`a0v-ecommerce-text-readonly-v1@1`，单模型、failover 策略但无 fallback 候选，绑定 `a0v-ecommerce-runtime-policy-v1@1`；task types 首批仅候选 `analysis.summarize/chat.answer/content.generate`，逐项验证输入输出合同后才可加入；10 个 capability 不整体映射文本模型，特别是 speech.synthesize/video.compose 不得借此变为 ready。
- Model 与 Route 都先用 placeholder gate 构造 evaluation candidate hash，Gate exact 指向该 candidate，再把 gate ref 写入最终 revision，沿用生产 Store 的 cycle-break 合同。

## 3. 模型评测

模型评测须区分传输健康、指令能力与业务质量。非空响应只证明基础传输，不能发布能力通过结论。固定无客户数据样本至少验证精确指令遵循、给定材料的来源引用和禁止编造字段；期望值及判定器在调用前冻结。策略合同测试分别记录，不用其数量稀释真实模型失败。健康验收另按同模型、同 modality、同 cutoff 的 3/3 要求执行；历史单条观察不能冒充 3/3。

经冻结清单批准的 live case 各有独立 0600 attempt journal；Secret resolve、Provider/plugin/policy exact readback 均在 journal `submitted` 前完成。每 case 最多 1 次、timeout 10 秒、max output 32 token，禁止保存 prompt、answer、headers、Secret 或 response body。任一 submitted 后结果不明时不得重发。仅满足健康验收完整证据时写入新的健康观察；不删除或复用历史 attempt journal。

## 4. 路由评测

Route Suite 使用固定 SELECT/BLOCK 矩阵，覆盖允许 task+text+capability、未知 task、错误输入 modality、错误输出 modality、缺 capability；只执行候选路由合同判断，不调用 Provider。所有 case exact match 且 threshold=1.0 后才发布 active Route。

## 5. 执行顺序

1. 默认 preflight；apply 强制 `aos_meta_head`、正租户 exact authority 与 canary=0。
2. 在任何 DB mutation 和 Provider 调用前生成独立数据库备份。
3. 验证真实价格来源后发布/回读 PriceSnapshot；缺来源时停止该依赖，继续无调用的合同实现与测试。真实评测按冻结样本清单逐个执行 receipt-first journal。
4. 登记 model dataset/suite/run/report/gate，发布 active Model。
5. 登记 route dataset/suite/run/report/gate，发布 active Route。
6. 写健康观察，回读 Price/Model/Route/Gates/Health exact refs，验证 canary=0。
7. 重放必须 Provider call=0、DB mutation=0、所有 exact ref 不变；总依赖审计如实报告剩余门禁，不以计数或单一文本路由宣称全部 capability ready。

## 6. 停止条件与风险

任何价格币种/非零边界、Provider/策略/hash、Eval target、Gate freshness、模型响应、token metadata、journal、数据库身份或 canary 漂移均 fail closed。已提交调用出现 timeout/transport/未知状态时停止本切片，不切换 Provider、不重发。

价格来源未核实、健康观察过期、模型业务评测未完成均为当前缺口。首链和八工作台的业务验收独立执行；不得以静态登记或测试通过代替。

## 7. 2026-09-11 重启复核与先行修复

### 用户最新范围修订：开发阶段不等待商业单价

用户明确授权开发、自测和接单验收不看模型成本，商业使用时再核算。此前将供应商单价作为当前开发主线阻断的顺序撤销。下一切片优先实现真实模型评测和正式运行接线；以显式开发费用延后核算合同承接授权，实际 token 用量照常持久化，费用保持未核价，不伪造零价或固定单价。商业默认 unknownPrice=block 保持原状；开发合同必须限定 org-org/dev-project、当前 exact 模型/审批及有效期，不能隐式扩展其他租户或发布为商业默认。

现有 ModelPriceSnapshot DTO 要求至少一个数值，BudgetPolicy 仅允许 unknownPrice=block，因此不能只配置开关或填 0 绕过。后续先形成跨 DTO/Resolver/Invoker/UsageReceipt 的完整最小施工卡，验证未核价能够被明确区分且重放不重复调用，然后编码；这项产品合同工作与无客户数据模型评测可串行推进，无需等待用户提供价格。

原隔离数据库已启动，2026-09-10T17:22:30Z 只读审计显示 providerHealth 为首个未满足门；active route/binding/agent 均为 0，canary 计数为 0。审计未执行 mutation 或 Provider 调用。

先行修复文件：`services/aos-api/aos_api/aip_r1_bootstrap_probe.py` 及 `services/aos-api/tests/aip/test_aip_r1_bootstrap_probe.py`。显式传入空审批集合必须拒绝全部请求；只有未传参数 None 才沿用旧默认。当前 `or` 会把空集合当成旧授权，违背失败关闭。先写失败测试，断言拒绝发生于 Secret resolve 和 transport 之前，再做单点修复，运行探针与 A0-V 健康回归。沿用现有 m1 A0-V Lease，不新增冲突租约。
