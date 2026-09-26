# W5caf｜旧 Single Ingress/Object 18432 专用 PG 回归方案

## 上位/证据

231 A0-V/BG-00 仍因真实 Fleet/历史行/Owner 门冻结。W5c5x/y 当前风险记录旧 Single Ingress 12 skipped、Object 2 skipped；W5cae 已证明 18432 旧 Journal 两文件 16/16，但不能替代这些模块。当前 `.venv` collect：`test_controlled_snapshot_ingress_pg.py`、`test_controlled_executor_integration_pg.py`、`test_snapshot_group_object_executor_pg.py` 共 **24 项**。三文件使用 `test_lifecycle_pg` 的 18432 opt-in、假源/假资产权威；不得读真实商城源。

## 文件级/环境最小清单

- 只读执行上述三测试文件及其现有 fixture；不修改任何生产/测试/迁移代码。若断言失败，冻结首个结果，另立最小修复方案，不能把失败吞成 skipped/green。
- 已有 `colima-aos-extension` 的 `aos-ar1c-pg` 起始应为 Exited 且 18432 无 listener；只临时启动此容器，`AOS_DOTENV_DISABLED=1`、`AOS_EXTENSION_PG_TEST=1`、无 `AOS_DATABASE_URL`，项目 `.venv`，900 秒单调有界单次运行。结束查 `ar1c_%` schema/role 残留并停回 Exited。18435 恢复真库、5433 另一专用库均不动。
- 产出本目录 verification，必要的 AOS 项目上下文/Prime 受管记忆与精确提交；不清理其他脏文件。

## 九步与停止

1. 复习 231、W5c5x/y 风险及三个旧文件的 opt-in/fake 合同。2. 先提交本方案。3. 核验容器/端口再临时启动。4. 唯一有界运行 24 项。5. 核对结果/资源并停回原状态。6. 18181 浏览器只读，8080 无业务验收。7. 复审代码方案一致性及真实 effect 不授权。8. verification 提交，CAS/共享/Prime 同步读回。9. 若 GREEN，下一波审计 `incomplete` 中“旧 PG skipped”的具体措辞并仅校准受证部分；若失败，下一波先修失败，不前移真实 A0-V。

即使 24/24 GREEN，也不证明 Store 跨事务原子围栏、全机 Host 排他、独立原始行或真实业务接受。230 L0 挂起、dev-org 仅零 canary、m1 单写不 push。
