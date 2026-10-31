# 价格、模型、运行策略与路由接续执行计划

## 目标

在不调用模型、不写当前业务数据库、不代签真人审批的前提下，复用现有 Owner 合同，生成可由本人真实会话核对的非签名材料。目标有效期为 `2027-03-31T04:00:00Z`，模型 `agnes-2.5-flash`，额度 100 元/日、1000 元/月。

## 步骤

1. 只读读取当前 Budget、Provider、BudgetPolicy、ModelPrice、RegisteredModel、RuntimePolicy 与 ModelRoute 的精确引用。
2. 只读确认 cost/window 的 proposal、decision、receipt、binding 当前状态；非零或 unknown 时只对账。
3. 依据现有 Pydantic/Owner 合同生成 `approval-material-schema.json`，禁止凭据和签名字段。
4. 生成 `material-draft.json`，状态固定为 `NON_SIGNING_NOT_SUBMITTED`；未知的原生 ID/hash 保持 `null`，不能杜撰。
5. 对草稿执行本地 schema 校验、授权值核对、敏感字段扫描与数据库无效应对账，输出 `verification.json`。
6. 对照当前 OpenAPI、本地监听端口与工作树候选源，输出 `formal-entry-map.json` 和 `formal-entry-readback.json`；源码存在但未进入 HEAD/冻结运行时，必须判为未可用。
7. 将材料交给本人真实会话审阅；没有本人原生决定前不进入任何提交、消费或发布动作。

## 现有接口与合同

- `aip_budget_cost_product.py`：原 cost 真人审阅请求恢复和单次私有派发。
- `aip_budget_policy_window_contracts.py`：预算/价格配对窗口草稿及 canonical hash。
- `aip_budget_policy_window_commands.py`：propose/decide/revoke/consume 精确 native wire 合同。
- `aip_model_governance_policy_contracts.py`：预算策略后继及开发成本授权边界。
- `aip_model_runtime_store.py`、`aip_model_runtime_contracts.py`：RegisteredModel、RuntimePolicy、ModelRoute 精确引用和发布边界。
- `routers/aip_model_governance_policies.py`：当前预算策略读取/发布及续期 source/checker 入口。

## 运行装载门

- 以 `127.0.0.1:18080/openapi.json` 为当前管理 API 已装载路由的读回证据，不以本地源文件推断运行可用。
- paired-window 必须通过受保护 `127.0.0.1:18468` 原入口；端口未监听时不得直连数据库、新建代理或用测试调用替代。
- 当前复核已证明 `policy-window-source` 未出现在冻结 OpenAPI，18468 也未监听；后续产品集成必须另立精确 Scope，先补方案与 RED，不在本材料任务中直接改脏工作树。

## 修改边界

本轮预期只写本证据目录与对应 D-waves 方案，不修改上述产品源码。若现有合同不能表达最新授权，必须先补方案、登记明确源文件 Scope、写 RED，再做最小实现。

## 测试

- JSON schema 可解析且拒绝额外字段。
- 截止时间精确为北京时间 2027-03-31 12:00。
- 模型、币种、日/月额度精确一致。
- 草稿不得出现 `approved`、真实 decision/receipt、bearer、Cookie、密码、token、SCRAM、私钥或签名。
- 当前数据库与运行状态只读前后指纹一致；Host/worker/Provider/model invocation 均保持 OFF。
- 正式入口地图与当前 OpenAPI/监听端口一致；未装载入口明确失败关闭。

## 停止条件

- 当前引用或父状态与本轮冻结不一致。
- 需要读取凭据、商城源或私人身份信息。
- 出现 CAPTCHA、登录失败、账号风险或需要本人原生审批。
- 任一外部动作返回 unknown。

上述条件只停止对应动作，不缩减长期 Goal；其余安全只读准备可继续。
