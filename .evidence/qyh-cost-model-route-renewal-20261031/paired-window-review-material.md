# Paired 预算/价格窗口审阅材料（非签名 · 未提交）

**前置：** cost 父链 native propose → decide → consume 完成且只读回读一致后，才可执行本链 POST。  
**租户：** `org-org` / `dev-project`  
**网关：** `http://127.0.0.1:18468`（`writerEnabled=false` 时仅查询/受控入口；写入须真人 native）

## 1. 目标窗口

| 字段 | 值 |
|------|-----|
| effectiveUntil | `2027-03-31T04:00:00Z`（北京 2027-03-31 12:00） |
| effectiveFrom | **办理时**由 Owner 读取当前时间，须落在 cost 父预算窗口内；方案阶段不填 |
| 绑定 | 预算策略后继与价格快照后继必须 **同一 targetPairHash** |

## 2. 后继资产 ID（语义不变，仅换窗口与引用）

- 预算策略：`a0v-ecommerce-budget-policy-v1`（新 revision 由 Owner 分配）
- 价格快照：`a0v-agnes-2-5-flash-development-deferred-v1`（新 revision 由 Owner 分配）
- 模型仍为 `agnes-2.5-flash`，日/月额度仍 100/1000 CNY

## 3. 串行 native 路由（18468）

1. `POST .../propose` — maker 发起；须带 `Idempotency-Key`
2. `POST .../decide` — checker 真人批准/拒绝
3. `POST .../consume` — 在 decide 批准后消费配对窗口
4. `GET .../requests/{operation}/{idempotency_key}` — unknown/unresolved 时 **只查不重发**

Web 面板：`/aip/model-runtime` 底部 **BudgetPolicyWindowReviewPanel**（直连 18468 CORS）。

## 4. 必填父链引用（办理前从 cost GET 填入，禁止杜撰）

- `costProposalId` / `proposalHash`
- `decisionId` / `decisionHash`（若适用）
- `consumptionReceiptId`（consume 后）

当前占位：`paired-window-review-material.json` 中均为 `null`（native 账本 0/0/0）。

## 5. 禁止

- 绕过 18468 直连数据库
- 在 cost 父链未完成时 POST window
- bearer/Cookie/密码/SCRAM/私钥/签名写入材料

---

**状态：** 预备审阅；**不等于** paired 已 propose/decide/consume 或经营验收。
