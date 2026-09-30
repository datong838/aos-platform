# W5CB4 BG00cw｜专用 issuer DB 工厂与进程启动检查文件级方案

## 上位依据与当前缺口

231-4 要求非 owner/非 BYPASSRLS 专用连接和事务租户，231-5 要求 checker 当前成员同事务重验；BG00cj 的 DB 触发器只接受固定 issuer LOGIN/role，BG00cm 在隔离克隆证明 TCP SCRAM、Event/Proposal 可受控写且 maker 写拒绝。BG00cv 已有私有 Unix transport，但尚无由可信启动器注入的 issuer 专用连接工厂和实际进程；普通 API 的 `db_connect` 是 owner/开发路径，不得复用。

## 本波文件级顺序

1. 新增 `services/aos-api/tests/aip/test_aip_network_issuer_connection.py` RED：专用 config 只接受 loopback、exact 数据库、私有0600 passfile/0700 parent、固定 `aos_network_approval_issuer` LOGIN；拒绝普通 `AOS_DATABASE_URL`/owner、错库、错租户、继承/特权/owner 角色。隔离 BG00cm 克隆真实 TCP 只读连接核对 session_user/current_user、scope；决定连接仅在回滚事务中核验角色，不发 Event。
2. 新增 `services/aos-api/aos_api/aip_network_issuer_connection.py`：在 issuer 进程内以显式 host/port/db/passfile 建立 psycopg 连接；事务开始前配置 SERIALIZABLE 决定或 READ COMMITTED/只读查询，随后现有 `apply_transaction_scope` 设 `SET LOCAL ROLE aos_runtime` 与 tenant GUC；逐项核验 database、session_user/current_user、rolsuper/bypassrls/inherit、owner membership 及 exact tenant。绝不读取 `AOS_DATABASE_URL`，不接收 wire 传入的 DSN。
3. `scripts/a0v_network_issuer_server.py` 只在文件级计划及 DB 工厂 GREEN 后新增：受限 CLI/配置读取，先执行 OS 身份、外部 OIDC、HBA 可信预检，再 bind BG00cv socket；当前同 UID/无正式 IdP 时应退出2，不启动 listener。若 HBA 证明不能由 issuer 自身可信读取，启动器必须失败封闭，不能接收可任意伪造的“已通过”字符串。
4. 专项/邻接、克隆只读/回滚、代码复审、verification、D-waves、精确提交及 authority/Prime 同步。正式实例角色/HBA/API 切换是另一个新备份+双克隆+零执行窗口波。

## 停线

本波不写当前库、不启自然 worker/Host/Provider、不发真实批准 Event；没有独立 OS issuer 用户、外部 IdP、当前第二 checker 时，进程不能启动为正式服务。隔离克隆与测试账号不能冒充当前真实业务授权。
