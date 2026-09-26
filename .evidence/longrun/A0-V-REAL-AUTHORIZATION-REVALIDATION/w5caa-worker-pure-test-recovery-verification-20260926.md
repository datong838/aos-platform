# W5caa｜Worker 纯测试历史环境错误重验 verification

1. 复习 231 A0-V→A1、230 L0、W5c8h 当时 5433 连接失败/10 项 setup ERROR、W5c8i 隔离撤旧入口与 W5ca9。现状风险只针对此测试结果，不推断真库迁移。
2. 方案 `m1@e5bcfe62` 先提交；只读检查 `test_analysis_data_requirement_worker.py` 的 stub/monkeypatch：无真实 PG/Source/Provider 调用。
3. 用项目 `.venv`、`AOS_DOTENV_DISABLED=1`、`pytest --noconftest` 单文件测试，完全不加载 session 级 PG fixture，也不设置共享库开关。
4. 正式结果 `11 passed, 6 warnings in 6.49s`；从历史 10 项变为 11 项是 W5c8i 新增 `test_direct_legacy_reconcile_is_frozen_before_route_or_coordinator`，不是数量漂移。六个警告为现存 Pydantic 字段 shadow。
5. 本波没有代码变更，无新增逻辑需另做累计；该单文件完整覆盖空目录、正常双 Receipt、unknown 冻结、claim/reject、结果不明、旧 reconcile 入口、范围轮转、取消与 Host lifecycle。`git diff --check` 与记忆校验在收口完成。
6. 8080 无 listener，18181 仍 PID36529、`/docs` HTTP200；无业务浏览器验收。
7. 仅关闭 W5c8h 的“纯 Worker 测试从未执行”债；真实 `a0v_096` 未迁、旧函数真库权限/同事务 Host+源组正向对账/原十二 Run closure 仍无权威。
8. verification、D-waves、AOS/Prime CAS、精确提交；不 push。
9. 下一波继续可独立证明的安全债，A0-V 外部 Fleet/历史行或正式退休业务决策仍是主门。

230 L0 挂起、商城源不读、dev-org 零 canary、unknown 不重发、不手工 run_definition、m1 单写。
