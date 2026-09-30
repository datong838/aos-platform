# W5CB4 BG00cu｜单次决策组合验证

- 基线：m1 `46e69f61`、AOS-000950；任务 Receipt `W5CB4-BG00CU-20260930`；文件级方案 `w5cb4-bg00cu-single-decision-composition-plan-20260930.md`。
- RED：`AOS_TEST_USE_SHARED_DATABASE=1 services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_aip_network_issuer_service.py` 退出1，新 `issue_decision_once` 缺失，2 failed/3 passed/1 skipped。
- GREEN/邻接：带显式隔离证明目录运行 service/attempt/auth/reconcile/network producer 五文件，退出0，`37 passed, 2 skipped`；compileall、diff check 退出0。
- 顺序与负例：Command 先外部认证→BG00ct 私有持久 Receipt→最多一次 BG00cn decide→BG00cq 精确 Event 只读回读；异常或查询失败返回 UNRESOLVED（有已落盘 attempt，不能重发），同 key 第二次在 reserve 阶段拒绝。隔离克隆以真实 issuer read-only LOGIN/role 查 Event0 的断联路径返回 UNRESOLVED，单次 decide 用受控异常替身，未产生 Event。
- 方案/代码复审：现网路由/数据库/迁移未改，`dispatch_issuer_request` 的 DecisionCommand 仍禁入；新增 `issue_decision_once` 仅供未来独立进程显式调用，工厂与私有目录均必须由可信 launcher 注入。测试不证明正式 JWT、当前 checker、正向 Event 或私有进程验收。
- 未完成：正式独立 OS 用户/私有 IPC、IdP/JWKS、当前 HBA/第二 checker，以及正向 Approval Event、八配置和首链仍缺；当前实例保持只读，Host/worker/Provider 关闭。下一波 BG00cv 专门完成私有进程与 OS/凭据接线的隔离负例，再择独立恢复波切换正式实例。
