# 本人在 Web 办理 cost 父链（助手不代 POST）

**入口：** [http://127.0.0.1:18434/aip/model-runtime](http://127.0.0.1:18434/aip/model-runtime) → 下滚 **「费用风险审核与恢复」**  
**租户：** org-org / dev-project（须已登录，不必重复登）

## 顺序

1. **独立复核费用提议（decide）** — 需 checker 身份；或先由 maker 创建提议（若产品流要求先 POST 提议，仅本人在此页操作）。
2. **启用已批准预算（consume）** — 在 decide 批准且未过期后。
3. **生成费用配置（configure）** — 在 consume 回执 observed 后。
4. 每步若返回 **unknown/unresolved**：用同 **提议 ID + 原 Idempotency-Key** 点 **「查询费用原请求」**，禁止重复 POST。

## 办理后

把 **proposalId**（可打码中间段）告诉助手，用于只读 GET 对账与 paired-window 材料填父引用；**不要**发送密码或 Token。

## 对照材料

- `cost-parent-review-material.md`
- `paired-window-review-material.md`（cost 完成后才办 window）
