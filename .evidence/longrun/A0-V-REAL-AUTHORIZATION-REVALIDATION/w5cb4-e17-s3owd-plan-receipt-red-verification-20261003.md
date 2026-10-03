# W5CB4 E17-s3o-w-d｜Plan 与共享 Receipt RED 核验

日期：2026-10-03。代码起点 `m1@7fb950df`，真实库 `aos_current_preview_20260927@a0v_135` 只读；隔离 `aos-ar1c-pg:18432` 临时 schema，测试结束自动删除。未改 API、Web、迁移、正式 ACL、Host/worker/Provider。

## 文件与结果

- 方案：`w5cb4-e17-s3owd-plan-receipt-red-plan-20261003.md`。测试：`services/aos-api/tests/extension_runtime/test_plan_receipt_issuer_red_pg.py`。真实 `w2_002` Plan ACL/RLS、原 `w2_001` 共享 Receipt DDL/ACL 与 `AipProductionContractStore._receipt` 写法，使用 `SET SESSION AUTHORIZATION aos_runtime`，未以 owner 身份执行受限断言。
- `AOS_EXTENSION_PG_TEST=1 services/aos-api/.venv/bin/pytest -q services/aos-api/tests/extension_runtime/test_plan_receipt_issuer_red_pg.py --tb=short --disable-warnings -rx`：exit 0，`1 passed, 8 xfailed`。两个 Plan head 直写及六种 generic/BI Receipt 伪造的拒绝预期均 strict xfail；内容草稿 `content_draft.register` 共享 Receipt INSERT 正向 1 passed。
- 用 `--runxfail -k 'directly_issue and generic'` 取消预期失败：exit 1，两个断言均 `DID NOT RAISE InsufficientPrivilege`。用 `--runxfail -k 'forge_original and create'` 单独执行：exit 1，Plan Receipt 写入同样 `DID NOT RAISE InsufficientPrivilege`。因此 xfail 指向真实宽权，不是夹具失效。
- 相邻 `AOS_EXTENSION_PG_TEST=1 services/aos-api/.venv/bin/pytest -q services/aos-api/tests/extension_runtime/test_plan_receipt_issuer_red_pg.py services/aos-api/tests/extension_runtime/test_plan_readonly_lock_protocol_pg.py services/aos-api/tests/extension_runtime/test_current_configuration_sources_pg.py --tb=short --disable-warnings --log-cli-level=ERROR`：exit 0，`23 passed, 9 xfailed`。其中旧只读 `FOR SHARE` 冲突仍 strict xfail。

## 失败、复审与下一步

- 首次测试因新文件漏显式导入 `database` fixture 报 setup error；补 `from test_lifecycle_pg import database` 后专项 exit 0。一次把两个 Alembic PG 测试并行执行触发共享 `aos_runtime` role DDL 的 `tuple concurrently updated`；改为顺序运行后重测，确认为 `DID NOT RAISE`，不把并行错误当产品缺陷。
- 方案一致性：本切片只给出发行权限 RED 和内容写路正向；原 Store 全部操作的真实前置依赖、successor 正向、正式 issuer/trigger/同键锁以及八配置/自然首链均未通过。需下一波先在隔离库为 Plan head/revision 和 operation 分流 Receipt 设计独立身份，逐项证原 generic/BI/successor/content 正反链；代码迁移头不能先于当前真库安全切换而提升。
- 浏览器本波不适用：仅底层隔离 PG 权限测试；上波 11:30 全栈真实浏览器验收见 `w5cb4-current-latest-20261003-1130-14a-restart-verification.md`。当前服务健康不能替代本波失败的发行权限门。
