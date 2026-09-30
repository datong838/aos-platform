# W5CB4 BG00cl｜网络审批独立签发入口文件级方案

## 上位依据和现状

复习 231-4 的数据库非 owner 专用角色、固定 search_path 与权限边界，231-5 的真实人类审批、精确绑定、幂等和未知结果先对账，及 BG00ci/BG00cj/BG00ck。当前代码和权威库均为 `a0v_118`，网络 ApprovalEvent 的 DB trigger 只接受 `session_user=aos_network_approval_issuer` 且 `current_user=aos_runtime`。该角色默认 `NOLOGIN NOINHERIT`，无密码和独立进程；`decide_network_activation()` 仍使用通用连接。当前 API 用 `aos_app`，没有已核验的外部 OIDC/第二 checker，安装 approved 但 binding0。因此网络审批正向和首链均未获准。

只读查询当前库和 BG00ck 克隆的 `pg_hba_file_rules` 都发现 local、127.0.0.1、::1 的通用 `trust` 规则；仅设 SCRAM 密码无法阻断本地免密登录。先处理此项独立安全门。

## 本波范围与文件顺序

1. 先对 `scripts/a0v_network_issuer_hba_gate.py` 写 RED：只读解析 PG `pg_hba_file_rules` 的有序首匹配，要求对 issuer 的 Unix socket、127.0.0.1、::1 可达规则全部由明确的 issuer 专用 `scram-sha-256` 覆盖；任何匹配 `trust`、`peer`、`md5`、异常或不可判定规则都失败封闭。用当前库和克隆只读负例证明拒绝，不能为通过测试先把当前角色设 LOGIN。再在新独立 PG 克隆中证明普通 runtime 不能造网络批准；临时授予专用测试凭据后只允许通过 TCP/SCRAM 登录、`SET LOCAL ROLE aos_runtime` 和精确 tenant 事务签发；跨租户、伪 checker、失效或重放请求必须拒绝。测试只触及独立克隆；当前权威库保持只读。
2. `services/aos-api/aos_api/aip_network_policy_action_producer.py`：把网络 `decide` 的连接源改成显式专用 issuer 入口。默认缺配置时失败封闭，不能回退 `db_connect` 或 `aos_app`。调用前必须完成当前外部 OIDC Principal、组织成员、maker/checker 分离与精确 Proposal/preview/hash 校验；事务由专用连接执行 Event、Proposal、Draft、ActionEvent 的原子更新，沿用现有幂等键与 Receipt 语义。不得在通用 API 进程环境放入 issuer 密码。
3. 新增独立 issuer 启动/连接模块与 `services/aos-api/tests/aip/` 专项：私有 0600 凭据文件、主机/库/角色白名单、TLS/SCRAM/HBA 只读预检、DB `session_user/current_user` 与非 owner 权限检查；测试先 RED 再最小实现。若当前架构无法隔离进程与凭据，先落只读预检及负例，不在当前实例启登录，也不宣称正向完成。
4. 只在独立克隆做正反与邻接回归，复审 231-4/231-5 一致性，记录实际命令/退出码/风险。当前实例的专用角色启登录、外部 IdP、第二真实 checker、API 切换和 Host 启动均另需可核验授权与独立切换波。

## 止损和完成判据

任何生产当前卷 DDL/DML、测试身份代替正式人、dev-org 写入、手工 Run、旧 12 Run 回放、商城源读取、Provider/worker/Host 启动都禁止。只有隔离克隆中的真实 TCP 登录与完整网络批准事务可以证明代码正向；单元 mock、superuser `SET SESSION AUTHORIZATION` 和 HTTP 200 均不算正式链。若发现现有 `AipActionStore.decide` 无法在非 owner 角色下原子通过，先记录 RED 和最小权限缺口，再改最小点，不扩大所有 Action 权限。
