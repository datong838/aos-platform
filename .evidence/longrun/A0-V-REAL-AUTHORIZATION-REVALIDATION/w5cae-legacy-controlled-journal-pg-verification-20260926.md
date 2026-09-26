# W5cae｜旧 Controlled Journal 18432 隔离回归核验（2026-09-26）

方案 `a754f4a4` 先行。只补 W5cad 相邻运行中因专用 18432 opt-in 门跳过的两文件，不连接 5433 业务 fixture 或 18435 恢复真库。

## 九步证据

1. 复习 231 A0-V/BG-00、W5cad、`test_lifecycle_pg.py` 的 `AOS_EXTENSION_PG_TEST=1` 与固定 18432 夹具。`pytest --collect-only` 两文件共 16 项。
2. 文件只有本 plan/verification；生产、测试、迁移代码零改动。
3. `aos-ar1c-pg` 启动前为 Exited (255)、`127.0.0.1:18432` 无 listener；容器无 mounts、RestartPolicy=no。只启动该现存容器，确认 127.0.0.1:18432 与 `pg_isready`；未动恢复真库容器。
4. 项目 `.venv`、`AOS_DOTENV_DISABLED=1`、`AOS_EXTENSION_PG_TEST=1`、未设置 `AOS_DATABASE_URL`，单次 600 秒单调有界运行两文件：**16 passed，7 warnings，6.74s**；runner `CHILD_EXITED`、child/runner exit0、未超时、15.349s。没有把先前的 16 skipped 冒充通过。
5. 夹具结束后专用库 `ar1c_%` schema=0、role=0；将 `aos-ar1c-pg` 停回 Exited (0)，18432 无 listener。之前 W5cad 的 5433 夹具 3 passed/相邻 9 passed 属不同一次性数据库，不合并为同会话单库总分。
6. 内置浏览器只读复核 18181 Swagger `aos-api 0.3.0`/OAS 3.1，8080 业务服务仍离线；未点击 Authorize 或任何执行请求。仅 `BROWSER_PARTIAL`，不能验收真实业务。
7. 方案与执行一致：旧 Journal/CompletedInput 的 fake asset authority 路径回归 GREEN，但不能证明当前全机 Fleet、Owner/Store effect、非空商城源、原 12 Run 或 A0-V 真实准入。34 项 current incomplete 不因本波测试消除。
8. 本 verification 提交后，更新 AOS 项目上下文与 Prime 受管记忆并读回，保留无关脏文件、不 push。
9. 下一波：审计其余旧 PG 跳过项与真实外部门禁，只做安全且能缩小技术风险的工作；无 Fleet/历史行证明或正式不接受业务结果的退休选择，不执行真实 closure/ACK/replay。230 L0 挂起，dev-org 只作零 canary。
