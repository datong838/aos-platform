# s3o-w-w 第一切片｜BI 发行数据库登录身份门

## 上位合同与现场事实

- 231-3/231-9、E17 D-wave、620 要求原 Plan/Receipt 只能在正式独立发行身份与当前安装/权限同事务下写。当前权威库 `aos_bi_plan_issuer` 角色/四个 a0v_136 函数为0，六目标 AgentInstance 行存在但 active0；公开 BI HTTP 继续503。
- 原签名 Growth1.13 全 schema 一次性库中已有 test-only `aos_bi_plan_issuer` 独立非 owner 登录与原 Plan/Receipt 正向，但连接由测试直接传 password；正式代码暂无受保护凭据/固定 DB 身份连接门。现有 `aip_network_issuer_connection.py` 的网络发行角色/SET ROLE 不可挪用为 BI 登录。
- 本切片只补 BI 专用连接边界，不创建当前角色/凭据或应用 migration，不接公开 HTTP。真实库只读；所有正向只在一次性克隆进行。

## 文件级施工

1. `services/aos-api/tests/aip/test_aip_bi_plan_issuer_connection.py` RED：配置要求本机端口、规范 DB、独立进程拥有的 0700 目录/0600 passfile；拒共享 owner/runtime login、super/BYPASSRLS/INHERIT、owner/runtime 成员、错 DB/scope/只读属性及 PG* 环境覆盖。真实 disposable PG 的 `aos_app` 错身份读连接必须拒绝。
2. `services/aos-api/aos_api/aip_bi_plan_issuer_connection.py`：固定 `aos_bi_plan_issuer` 登录及显式本机 host/port/DB/passfile，读连接 REPEATABLE READ+read_only、写连接 SERIALIZABLE；事务本地双租户绑定后核 `session_user=current_user=issuer`、角色属性/成员/超时，连接失败统一禁入。无默认 DSN、无口令参数/日志、无重试。
3. `services/aos-api/tests/extension_runtime/plan_restricted_issuer_case.py`：在原签名 full-schema 测试已创建的 test-only 发行角色窗口，以私有临时 passfile 调用新连接门核真实独立登录/作用域/只读禁写；原服务正向保持。该克隆证据不能当当前正式登录。
4. 专项、原签名全 schema（显式一次性 PG/OCI/Growth1.13 回执）及相邻 network issuer/BI 编排回归；代码/方案复审、verification、精确提交、D-wave/621/Authority/Prime。

## 下一门与回滚

- 后续有限私有 Unix 进程须由不同 OS UID 持有 passfile/socket/attempt 目录，并用本连接门构造原 BI 服务与只读 Reader；还须正式 IdP、四函数/ACL migration、六 active Agent、全链恢复与零执行窗口。失败关闭 HTTP 503，不用测试凭据接当前实例。
- 若测试门不符或身份不可校验，保留失败证据，撤本切片新代码/测试提交即可回退；不碰当前数据库或卷。
