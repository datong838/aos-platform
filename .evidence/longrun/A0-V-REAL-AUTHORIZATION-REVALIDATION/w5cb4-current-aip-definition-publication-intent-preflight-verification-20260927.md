# W5CB4 当前定义发布 intent 前置只读核验（2026-09-27）

## 第 1–7 步：方案、最小实现、测试与现场

- 先读 231 A0-V/A1、产品方案 9.3、`7c377876` adapter verification 和当前 `AOS-000802` 强一致状态；plan 见同目录 `w5cb4-current-aip-definition-publication-intent-preflight-plan-20260927.md`，代码落点与计划一致。
- 新的纯分类器仅接受三表行投影：全空 `EMPTY`，6/37/10 目标 ID、revision=1、source=1.11.0、非空 hash 的结构全量为 `COMPLETE`，部分/异源/重复/错版本/缺 hash 为 `FREEZE_PARTIAL_OR_CONFLICT`。`COMPLETE` **不证明 hash 与签名包 exact 相等**，只能只读报告；未来写许可仅在 `EMPTY` 且额外 exact 门全通过时才可能成立。
- 专项加累计 28/28 通过，包括旧发布器兼容、signed 前置、来源单选；`git diff --check` 通过。当前新库只读事务回读 agent=0、skill=0、capability=0、runtime_binding=0，分类为 EMPTY，但本波未取得唯一 intent，也未执行任何定义发布。
- HTTP 8080 `/openapi.json` 200、8434 `/aip/model-runtime` 200；浏览器读回仍显示跨页权威投影 `ecommerce agent definitions differ from 6-role authority`，六角色未 ready、草稿空白、模型路由 0。这是预期禁入，不是功能绿或正式发布验收。

## 第 8–9 步：一致性、风险和下一波

- 只新增纯分类器/测试，未读商城源、未碰原 12 Run、未启动 Runtime/worker、未删除旧卷或写新库；preflight 不可独自调用发布器，`EMPTY` 不等于批准。
- 下一波实现唯一 durable intent、精确目标数据库连接工厂、同写边界签名重核、53 行 Owner 发布与逐行独立回读的受控脚本；先隔离 PG 测试。未知/部分提交只读冻结，不自动重发或“补齐”。若当前 API 测试夹具仍依赖不存在旧签名目录，改用当前专用夹具，不恢复旧卷。之后才可考虑当前库正式单次执行。
