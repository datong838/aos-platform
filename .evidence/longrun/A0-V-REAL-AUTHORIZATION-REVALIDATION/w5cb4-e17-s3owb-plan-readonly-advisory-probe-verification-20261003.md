# W5CB4 E17-s3o-w-b｜Plan 只读版本协调隔离探针

日期：2026-10-03；方案为 `w5cb4-e17-s3ow-readonly-source-version-plan-20261003.md` 的 s3o-w-b 段。只在 `aos-ar1c-pg:18432/postgres` 临时 schema 创建测试触发器，不含正式 migration、当前库、正式身份或 Host 启动。

- `AOS_EXTENSION_PG_TEST=1 services/aos-api/.venv/bin/pytest -q services/aos-api/tests/extension_runtime/test_plan_readonly_lock_protocol_pg.py --tb=short --disable-warnings`：exit0，1 passed。`test_plan_readonly_lock_protocol_pg.py` 使用非 owner 会话 `SET SESSION AUTHORIZATION`，其 runtime 角色对 Plan head 仅 SELECT。读事务先取稳定 `(org,project,plan)` advisory 锁、普通 SELECT 当前版；数据库 `BEFORE UPDATE` 触发器对同键取锁，第二连接更新在250ms超时为 `QueryCanceled`；读事务结束后相同 UPDATE 成功且版本推进到2。
- `git diff --check` 与 `py_compile` 针对本波测试：exit0。该探针证明数据库强制锁可以替代 Host 对原 Plan 的行锁写权限，并通过真实双连接时序反证。

边界：只有 UPDATE 一个触发时序被证；INSERT/DELETE、所有原 Store create/revise/freeze、Receipt 同事务、同键重放、跨租户和并发多 Plan 顺序仍未证明。原四源读者仍是 `FOR SHARE OF h`，当前 runtime Plan/Receipt ACL 仍宽，本波不能宣称独立 issuer、正向配置或首链。下一步先文件级方案核所有原写路径，隔离专用发行角色及触发器覆盖，再决定是否提出独立 migration；当前库切换需全备、克隆全链和零执行窗口。
