# W5CB4 BG00cj｜网络审批签发者 DB 门隔离验证

## 基线、RED 与最小实现

接 BG00ci，当前权威库 `aos_current_preview_20260927@a0v_117` 继续只读；代码基线 `b2ab0867`。方案见同名 `plan`，初始 RED 见同名 `red`。在独立 Colima `aos-a0v-test-only` 的 `aos-bg00ce-isolated-pg` 及其独立命名卷上，针对 `a0v_117` 运行新测试：普通 `aos_runtime` 可直接 INSERT 网络 ApprovalEvent、UPDATE 网络 Proposal 哈希，2 failed。首次 pytest 命令未设置 `AOS_TEST_USE_SHARED_DATABASE=1`，仓库 session fixture 曾在默认测试实例创建/删除 disposable 测试库；当前权威库未写。随后显式设置该标志，只使用隔离容器，RED 仍为2 failed，退出1。

`a0v_118_network_approval_issuer_gate.py` 只增加网络专用触发器。Event 仅可由精确 `session_user=aos_network_approval_issuer` 且 `current_user=aos_runtime` 插入；网络 Event 更新/删除全拒。网络 Proposal 只允许状态、版本、更新时间变化；初始必须 `drafted`/version1/绑定哈希齐全；签发者不得冒充 maker 创建网络 Proposal。新角色默认 `NOLOGIN/NOINHERIT`，无密码、无数据库 CONNECT；精确复用现存同属性角色，发现角色或成员关系漂移拒绝。通用 Action 不改。触发器为 invoker、固定 search_path、函数 EXECUTE 从 PUBLIC 撤销。

## 隔离库结果

从迁移文件 `upgrade()` 提取原始 SQL，在隔离库事务中应用；其后针对修改过的 trigger function 做精确 `CREATE OR REPLACE`，将测试角色恢复为与最终迁移一致的 `NOLOGIN` 且撤销 CONNECT。当前隔离库回读 `a0v_118`、触发器2、`rolcanlogin=f`、Proposal/Event计数均0。当前权威库回读仍 `a0v_117`。

- `AOS_TEST_USE_SHARED_DATABASE=1 AOS_BG00CJ_TEST_CONTAINER=aos-bg00ce-isolated-pg services/aos-api/.venv/bin/pytest -q services/aos-api/tests/aip/test_aip_network_policy_approval_issuer_pg.py services/aos-api/tests/aip/test_aip_network_policy_contracts.py --disable-warnings --tb=short`：17 passed、7 warnings，退出0。覆盖普通 runtime 伪造 Event/核心哈希拒绝、网络 Event UPDATE/DELETE 拒绝、签发角色事务内正向插 Event 与状态变更、签发者不能创建 maker Proposal、`NOLOGIN` 实际登录拒绝，以及通用 Action 表路径可插 Event。所有测试写入均在隔离库事务中回滚。
- 角色复用预检在隔离库执行退出0；同事务临时改为 LOGIN 后预检以 `NETWORK_APPROVAL_ISSUER_ROLE_DRIFT` 退出3，事务自动回滚、`rolcanlogin` 回读仍 `f`。临时新角色创建分支在事务中输出 `f|f` 后回滚。`python -m py_compile` 两文件、`alembic heads`=`a0v_118`、精确 `git diff --check` 均退出0。
- 正向签发测试用隔离库超管 `SET SESSION AUTHORIZATION` 仿真角色拓扑，不能证明真实 issuer 凭据、独立进程或人类 checker。当前 PG 容器本地 `trust`，正式启 LOGIN 前必须配置独立 SCRAM 凭据并拒绝该角色本地 trust；当前实例不启用。

## 复审与剩余门

本波仅证明数据库网络专用防伪门在独立克隆有效。没有执行完整 Alembic 从干净备份恢复后的升级链；没有当前库迁移、API issuer 进程、真实外部 OIDC/第二 checker、审批正向业务链或浏览器验收。当前代码迁移头高于当前库，下一波 BG00ck 必须先做一致备份可恢复、独立全库克隆升级/回读、零执行窗口，再决定当前库迁移与重启；缺任一门则保持当前服务禁入且不可称最新版本已运行。后续 BG00cl 建隔离 issuer 进程/凭据与真实人类审批接线，不用测试角色作业务验收。Host/worker/Provider继续关闭；未读商城源、未重放旧 Run、未写当前库。
