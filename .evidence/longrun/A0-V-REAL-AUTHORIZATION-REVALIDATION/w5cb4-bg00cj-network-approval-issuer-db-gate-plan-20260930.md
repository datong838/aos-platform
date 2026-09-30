# W5CB4 BG00cj｜网络 ApprovalEvent 专用签发者与 DB 门文件级方案

## 上位依据与现场缺口

复习231-4数据库非owner专用角色/签名命令、231-5真实人工审批与不重发边界，以及 BG00ch/BG00ci。当前 `a0v_117` 的 `aip3_001_action_control.py` 给 `aos_runtime` 通用审批表 `SELECT,INSERT`；当前库的实际授权还含 `UPDATE,DELETE`，`aip_action_approval_event` 和 `aip_action_proposal` 均无业务触发器。`AipActionStore.decide()` 在 Python 核 maker/checker 并直接插 Event、改 Proposal；`precheck_network_activation()` 会读 Event 和哈希，但普通 runtime 可在库层伪造前置证据。当前 API 仍为 `aos_app` 超管，不能用它证明 DB 隔离。

## 文件与顺序

1. `services/aos-api/tests/aip/test_aip_network_policy_approval_issuer_pg.py`：先在独立 `a0v_117` 克隆中 RED，证明普通 `aos_runtime` 不得 INSERT/UPDATE/DELETE 网络 ApprovalEvent、不得改网络 Proposal 的身份/策略/绑定等核心字段；通用 Action 的合法审批仍可行。测试显式检查 `session_user`、`current_user`、tenant GUC、SQLSTATE、事务回滚和两租户隔离，不借 owner 成功冒充 runtime 成功。此测试只用 `docker exec` 指向专用隔离容器；执行 pytest 时必须显式 `AOS_TEST_USE_SHARED_DATABASE=1` 跳过仓库自动建库/删库 fixture，并设置 `AOS_BG00CJ_TEST_CONTAINER=aos-bg00ce-isolated-pg`。首次 RED 忘记前一标志，fixture 曾在默认测试实例短暂创建/删除 disposable DB；当前权威库未写，后续禁止重复该路径。
2. `services/aos-api/alembic/versions/a0v_118_network_approval_issuer_gate.py`：独立数据库安全迁移。网络 Event 的 BEFORE INSERT/UPDATE/DELETE 触发器阻断普通 runtime，网络 Proposal 的 UPDATE 触发器锁定核心字段，现有历史网络 Event 若有则先只读盘点且不可悄悄改写。通用 Action 不受网络专用条件影响。专用签发角色默认 `NOLOGIN`，迁移不授予 CONNECT/密码；另波在独立凭据、SCRAM 与本地 trust 拒绝规则核验后才允许启登录与 issuer 进程。函数固定 search_path、撤销 PUBLIC，不能让 `SET ROLE` 或 GUC 自称签发者。不可逆 downgrade fail-closed。
3. `services/aos-api/aos_api/aip_network_policy_action_producer.py`、`aip_action_store.py` 及受限 API 启动器：使网络审批仅经独立签发连接/明确接口，当前 runtime 不能直接读取签发凭据；该路径要重新验证当前正式 OIDC checker、精确 Proposal/Event 哈希、幂等与事务原子性。缺真实 IdP/第二 checker 时只在独立克隆使用测试身份，当前实例不启用。
4. 同一克隆做正反全链：普通角色伪造拒绝，专用签发者合法审批、通用 Action 无回归，撤销/重放/跨租户/并发/角色切换拒绝；只读核当前真实实例仍 approved 安装、binding0、ApprovalEvent0。专项+累计、代码/方案复审、验证落盘后再决定正式库迁移。迁移头高于当前库期间每日门不得伪称最新已运行；当前库升级另波一致备份+全库恢复演练+零执行窗口。

## 本波边界

先完成现状盘点、方案与克隆 RED，不对当前库执行 DDL/DML，不创建当前实例身份，不启 Host/worker/Provider，不回放旧 Run、不读商城源、不写 dev-org。不得用仅检查 `current_user` 的可冒充 role/GUC 当作专用签发证明；角色拓扑与私密凭据隔离是实现前必须验证的门。
