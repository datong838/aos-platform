# GT-b4c-b2d｜原 Model Eval 申请自然到期与已占预算保留

基线 2026-10-02 05:16 CST，AOS-001095 / m1 `69ddd03b`。复习 231-5 §5–6、231-6、D-waves GT-b4c-b2d。权威库 `a0v_118` 只读；只在自动 disposable PG 测试。`aip_model_eval_budget_reservation` 当前 schema 仅 `held`，本波不伪造 `unknown`/发送/对账。

## 文件级计划

1. 最小扩展 `services/aos-api/tests/aip/test_model_eval_request_pg.py` 中已有 `seeded_approved_model_eval_request` 测试 helper，允许调用方给定较短的未来到期时长，默认30分钟不变；只用于测试真实持久申请和原 maker/checker 批准。
2. 在 `services/aos-api/tests/aip/test_model_eval_budget_reservation_pg.py` 增加 PostgreSQL 真时钟到期测试：先取得原批准并 hold，等待实际 `expires_at` 到期；重入 hold 必须拒绝，旧 hold/三桶 held 仍保留，不发生 release。另一个到期前未 hold 的申请到期后不能新占额。若 RED，定位原 request/approval guard 后做最小修复。
3. 专项和相邻回归、静态、方案/代码复审、verification、m1 精确提交及 AOS/Prime/D-waves 同步。无前端变更，浏览器本波不适用。

## 边界与剩余

真实库不迁移，Host/worker/Provider 不启，org-org/dev-project 唯一正向，dev-org 零副作用。当前 schema 没有 Eval `submitted/unknown` 与 Provider Intent，不能以此波证明 unknown 保留；后续 GT-b4b 共同容量与一次性 Intent 建立后，在原状态机测试。合法普通 Task/Action 自然来源同样仍需独立寻找。
