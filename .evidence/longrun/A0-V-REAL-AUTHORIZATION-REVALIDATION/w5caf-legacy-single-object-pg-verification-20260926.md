# W5caf｜旧 Single Ingress/Object 18432 专用 PG 回归核验（2026-09-26）

方案 `a20a66ad` 先行；上位 231 A0-V/BG-00 不变。

## 九步证据

1. 复习 W5c5x/y 的旧 Single/Object skipped 风险、`test_lifecycle_pg.py` 显式 18432 opt-in 与假源/假资产合同。当前三文件 collect=24。
2. 未改生产/测试/迁移代码；仅本方案与 verification。
3. `aos-ar1c-pg` 起始 Exited (0)、18432 无 listener；临时启动后仅绑定 127.0.0.1:18432，`pg_isready` 正常；未接触 18435/5433。
4. `.venv`、`AOS_DOTENV_DISABLED=1`、`AOS_EXTENSION_PG_TEST=1`、无 `AOS_DATABASE_URL`，唯一 900 秒单调有界三文件运行：**24 passed，7 warnings，20.31s**；runner `CHILD_EXITED`、child/runner exit0、29.082s，未超时。没有把 W5c5x/y 历史 skipped 当作此前通过。
5. 完成后 `ar1c_%` schema=0、role=0；容器停回 Exited (0)，18432 无 listener。W5cae 16/16 是另一独立会话，不合并成同一会话累计分母。
6. 内置浏览器只读核对 18181 Swagger `aos-api 0.3.0`/OAS 3.1；HTTP 200，8080 连接拒绝。浏览器 `PARTIAL`，未执行 API、不能证明业务链。
7. 旧 Single Ingress/Object fixture 自身 GREEN，仅可消除“这些文件当前仍 skipped”的叙述；其 fake 源/资产不证明真实商城数据、Store 跨事务 fence、全机 Host、原 12 Run 或 A0-V 准入。当前 34 项风险的真正生产未接线/真库未迁/外部证据缺口仍在；下一波逐项改写旧 skipped 字句时不得删除这些边界。
8. 本 verification 提交后更新共享/Prime 受管记忆与 AOS 项目上下文，读回；保留用户其他脏文件，不 push。
9. 下一波 W5cag：精确审计 current incomplete 21/22 中旧 PG skipped 残留措辞，用 W5caf/W5cae 证据缩减且保留真实 Store/Fleet/Owner 缺口；无新授权时不做真实 closure/ACK/replay。230 L0 挂起，dev-org 仅零 canary。

## 记忆读回

docs 上下文/受管记忆 `docs/m1@2cb14937`；CAS `AOS-000729→AOS-000730`，`delivery_status=W5CAF_LEGACY_SINGLE_OBJECT_24_OF_24_ISOLATED_GREEN_REAL_A0V_FROZEN`，下一门不变、`incomplete=34`。`memory-status` GREEN_WITH_WARNINGS：共享/上下文/Prime 强一致投影 CURRENT，Codex 注记 PENDING_ASYNC；`memory-validate` GREEN。无真实业务执行权。
