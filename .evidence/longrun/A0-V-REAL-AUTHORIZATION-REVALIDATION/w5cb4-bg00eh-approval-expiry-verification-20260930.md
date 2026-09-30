# W5CB4 BG00EH｜批准预检锁等待到期验证

基线 m1@27c38634、AOS-000996。按 plan 实施，仅 `aip_network_policy_approval_consumer.py` 新增7行，在 Guard 完成后、返回 Precheck 前用 `clock_timestamp()` 复核 Proposal/Event 到期；沿用原 EXPIRED 错误，无激活/迁移/权限改动。

| 验证 | 结果 |
|---|---|
| 初始测试夹具 | 两次 exit 1：先缺 meta_workspace 父行，再 issuer 的 SET LOCAL ROLE 在 Store commit 后失效。修复仅在一次性测试库创建父行、为不复用的测试连接保持 session role/scope；这两次不计产品 RED。 |
| 修正夹具后，旧生产代码运行 `pytest -q tests/aip/test_network_approval_precheck_expiry_pg.py --tb=short --show-capture=no` | exit 1；1 passed / 2 failed，两个失败均为 `DID NOT RAISE NetworkApprovalConsumptionBlocked`。已经观察 pg_stat_activity=Lock，且 DB clock 在释放 checker 行锁前跨过期限。 |
| 最小实现后，新增测试 + test_aip_network_policy_action_producer.py + test_runtime_configuration_candidates.py + test_configuration_authorization.py | exit 0；40 passed，7条既有框架告警，21.50s。包含 Proposal 到期、Approval 到期、未到期正向及 NetworkPolicy head/revision/receipt 数量不变。 |
| `python -m py_compile` 两文件；`git diff --check` | exit 0。 |

命令在 `aos-platform/services/aos-api` 使用 `.venv/bin/python -m pytest`。测试启用标准 session fixture，创建名称为 `aos_test_*_ti4_test` 的独立数据库并升级至代码 head，结束后清理该测试库；没有启用共享数据库开关。主体、Egress、批准均为明确测试夹具；Producer/Guard/Store、a0v118 Event trigger、PG锁和时钟是真实执行，没有替换 Guard 或时间。issuer session authorization 仅用于隔离代码路径测试，绝非正式身份/登录/业务批准证明。

复审：最后一次时间必须取 clock_timestamp，不能取 transaction_timestamp；检查仍处在当前事务持锁范围，Proposal 与 Event 核验完成后不复用过期入口时间。没有将只读 Precheck 升格为可持久授权令牌。实际原子消费者仍须在写入同事务重新核验全部依赖与时效，BG00EE 的非特权 owner/caller/issuer 隔离要求继续有效。此次没有页面或 API 接口变更，不涉及浏览器交互验收；当前服务未重启部署该提交。

下一波 BG00EI：复习 BG00EE 的完整原子消费合同，在隔离库制定并验证专用非特权函数 owner、窄 caller、独立 issuer 的权限矩阵，再实现最小同事务 Proposal/Event/依赖/Receipt 消费路径；保持普通 active INSERT 禁入。不得以合成测试角色取代当前正式凭据，不在当前库迁移。首链仍 pending。
