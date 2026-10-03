# W5CB4 E17-s3o-w-e｜独立 Plan/内容发行与只读锁隔离证明

日期：2026-10-03。起点 `m1@0a2f16ea` / Authority `AOS-001213`。目标、文件与边界见 `w5cb4-e17-s3owe-separated-writer-protocol-plan-20261003.md`。运行位置仅独立 `aos-ar1c-pg:18432` 的一次性 schema；测试角色 `s3owe_plan_*`、`s3owe_content_*` 测后清理。当前真库 `aos_current_preview_20260927@a0v_135` 只读，生产 migration 头不变。

## 可复核验证

- `AOS_EXTENSION_PG_TEST=1 services/aos-api/.venv/bin/pytest -q services/aos-api/tests/extension_runtime/test_plan_receipt_writer_protocol_pg.py --tb=short --disable-warnings --log-cli-level=ERROR`：exit 0，3 passed。两个独立 LOGIN/NOINHERIT/非特权角色均无表 owner 权；runtime 对 Plan head/revision/共享 Receipt 仅 SELECT，INSERT/UPDATE/DELETE 均无权限。
- Plan/内容两身份互相伪造 Receipt operation 均 SQLSTATE42501；runtime 直写 Plan 与 Plan Receipt 失败；内容 `content_draft.register` 原 INSERT 形状成功；Plan issuer 插 head/revision/原 Store Receipt、更新 head 成功；跨租户写和 DELETE 失败。
- 只读 runtime 先持 `(org,project,planId)` 事务 advisory 锁，原 Plan head 普通 SELECT 得到 version1；第二连接以 Plan issuer 更新同键在250ms内 `QueryCanceled`；读事务退出后同一 UPDATE 成功，version2。证明锁协议可协调，未替换原生产读者。
- 相邻 `set -o pipefail; AOS_EXTENSION_PG_TEST=1 services/aos-api/.venv/bin/pytest -q services/aos-api/tests/extension_runtime/test_plan_receipt_writer_protocol_pg.py services/aos-api/tests/extension_runtime/test_plan_receipt_issuer_red_pg.py services/aos-api/tests/extension_runtime/test_plan_readonly_lock_protocol_pg.py services/aos-api/tests/extension_runtime/test_current_configuration_sources_pg.py --tb=short --disable-warnings --log-cli-level=ERROR | tail -5`：exit 0，26 passed/9 xfailed。专项在将内容路径改为原 INSERT 形状后重跑仍 3 passed。`compileall` 与 `git diff --check` exit0。

## 复审与剩余风险

- 与方案一致：数据库身份、租户、operation 与事务锁均在独立 PG 可验证；测试角色和 trigger 仅是原表 ACL 的协议探针，不是正式账户、迁移或当前实例正向。读取的原配置 reader 仍 `FOR SHARE`，严格 xfail 未转 GREEN。
- 共享 Receipt 有其它合法 operation；本探针只映射 Plan 六操作和 `content_draft.register`，原 Store 的其它操作会被它拒绝。因此绝不能把当前 test trigger 直接做正式迁移。先盘全共享 Receipt operation 和对应原写者，并以独立受限连接运行 generic/BI/successor/content 完整原路径，证明原幂等/CAS、失败回滚、RLS 与零越权。正式迁移/切换还需新一致备份、ACL-faithful 克隆、零执行窗口及正式 OIDC/凭据。
- 本波只改测试/证据，没有 API/Web 功能变化；浏览器不适用。当前安装与首链状态继续按上波真实浏览器/权威库证据，不能用3 passed 代替业务通过。
