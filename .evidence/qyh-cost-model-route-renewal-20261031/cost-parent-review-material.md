# Cost 父链审阅材料（非签名 · 未提交）

**租户：** `org-org` / `dev-project`  
**状态：** `NON_SIGNING_NOT_SUBMITTED`  
**捕获时间：** 2026-10-31T17:24:00+08:00  
**authenticated 回读收据：** `.evidence/qyh-cost-model-route-renewal-20261031/authenticated-current-readback-r1.json`

## 1. 授权边界（材料侧，非 native 批准）

| 项 | 值 |
|----|-----|
| 模型 | `agnes-2.5-flash` |
| 币种 | CNY |
| 日额度 | 100 元（10000 minor） |
| 月额度 | 1000 元（100000 minor） |
| 接续目标截止 | 2027-03-31 12:00 北京时间（UTC `2027-03-31T04:00:00Z`） |
| 模型调用 | **禁止**（材料准备不等于运行许可） |

## 2. 当前精确引用（只读 GET，hash 与 prior 一致）

- **Budget** `a0v-ecommerce-hard-stop-budget-v1` rev **1** · hard-stop · 父窗口至 2027-09-10（总预算语义）
- **BudgetPolicy** rev **13** · **out_of_window**（短窗已过期，需 paired 后继）
- **Price** rev **12** · **out_of_window**
- **RegisteredModel** rev **12** · 仍引用过期 policy/price
- **RuntimePolicy** rev **13**
- **ModelRoute** rev **12** · resolution **blocked**（eval / 价目 / health）
- **Provider** `a0v-agnes-text-readonly-dev` rev **1**

## 3. Native 账本（只读对账，不得重发）

来源：`.evidence/qyh-post-renewal-binding-readonly-20261031/native-parent-confirmation-r2.json`，与本波 **无 POST** 假设一致：

- cost proposals：**0**
- cost decisions：**0**
- cost consumptions：**0**

若后续任一计数非零，**停止提交**，仅用原 `Idempotency-Key` 做 GET 对账。

## 4. 拟办理的原 cost 父链（本人会话批准前不得 POST）

**管理 API：** `http://127.0.0.1:18080`（经 Web `/api` 代理）

| 顺序 | 方法 | 路径 | 说明 |
|------|------|------|------|
| A | POST | `/v1/aip/budgets/cost-proposals` | 仅本人在浏览器/native 工具发起；须独立 maker/checker |
| B | POST/GET | `/v1/aip/budgets/cost-proposals/{id}/review-requests/decide` | decide 须真人；unknown → 同键 GET |
| C | POST/GET | `/v1/aip/budgets/cost-proposals/{id}/consumption-request` | 消费回执；unknown → 同键 GET |
| D | GET | `/v1/aip/budgets/cost-proposals/{id}/policy-window-source` | 只读父事实；**无** proposal_id 时不可用 |

**提议内容模板（canonical 字段，非已提交 hash）：**

- `schemaVersion`: 1
- `tenant`: org-org / dev-project
- `target.budgetId`: 保持 `a0v-ecommerce-hard-stop-budget-v1` 或后继预算 id（须与 Owner 合同一致）
- `target.revision`: 当前 head **1** → 下一 active **2**（`draft_revision` = 1，`expected_head_version` 以提交前 GET 为准）
- `target.dailyLimitMinor` / `monthlyLimitMinor`: **10000** / **100000**
- `target.hardStop`: **true**
- `basis.kind`: `development_risk_proposal`
- `basis.provider`: ProviderInstanceRevision ref rev **1**（见上）
- `basis.providerModelId`: `agnes-2.5-flash`
- `basis.perRequestRiskMinor` / `totalRiskMinor` / `maxRequests`: 须在日/月上限内，具体数值由本人批准前在 UI/合同中确认

**禁止出现在本材料或聊天中的内容：** bearer、Cookie、密码、SCRAM、私钥、签名、已生效的 proposalId/decisionId。

## 5. 本人审阅勾选（native 前）

- [ ] 租户仍为 org-org / dev-project
- [ ] 日/月额度与 2027-03-31 授权一致
- [ ] 接受「先 cost 父链 → 再 paired window → 再 model/policy/route 后继」顺序
- [ ] 理解 classic renewal **不会**自动修复 price/model/route
- [ ] 确认 native 账本仍为 0；若非 0 则改只读对账
- [ ] 批准前 **不**启用 Host/worker/Provider/模型调用

## 6. 下一材料门（仍非签名）

cost 父链 native 回读一致后，才生成 **paired policy/price window** 非签名材料（`effectiveUntil` 固定 UTC 2027-03-31T04:00:00Z，`effectiveFrom` 办理时由 Owner 读取，方案阶段不伪造）。

---

本页仅供核对；**不构成提议、决定、消费或阶段验收。**
