# E17-s3o-g｜独立 Assignee 发行身份与窄 ACL 隔离计划

基线 `m1@9710f1ec`、`AOS-001191`。已复习 231-4/231-9、s3of RED、现有 Network/Budget 独立 issuer 连接及原 `AipAssigneeResolutionStore`。本波只在 test-only Colima 上由 pytest 自动新建/删除 disposable DB；**代码 Alembic head 保持 a0v_135，当前真库不迁移**。仅闭合 Assignee Receipt 单表的隔离证明，不宣称 Registry/三 Binding/正式 API/Host 成功。

## 文件级范围

- `services/aos-api/tests/aip/test_e17_s3of_issuer_acl_pg.py`：原 strict xfail 是 RED；扩为隔离测试，先证正向 scope 下普通 runtime INSERT 被拒，再以独立登录/私有测试凭证让原 Resolver `resolve` 成功，负例含错误登录、无私有凭证、跨租户、Receipt UPDATE/DELETE。修复后移除 xfail。
- `services/aos-api/aos_api/aip_assignee_issuer_connection.py`（新增）：仅注入原 `AipAssigneeResolutionStore(connect_factory=...)` 的独立连接；配置要求回环 host、精确库、0600 passfile/0700 parent、非 owner/non BYPASSRLS 登录、固定身份、受限超时、同事务租户 GUC、非只读写连接。不得读取 API DSN/环境 PG 密码，缺配置失败关闭。不复用 Network/Budget 的实际发行身份。
- 原 `aip_assignee_resolution_store.py` 优先不改；若原 `resolve` 的提交/读回行为需要连接包装，只加最小逻辑，不重写 Resolver 算法。`aip_agent_registry_store.py`、Skill/Capability/Tool Binding 其他权限不在本波改变。
- 本波隔离 fixture 内临时 SQL：在 disposable DB 上对 Assignee Receipt 显式 REVOKE runtime INSERT/UPDATE/DELETE；建立 test-only 独立登录，赋予它经最小表权限可运行原 Resolver 的权限和租户 RLS，Receipt 只 SELECT/INSERT，测试结束撤连接并清理角色。正式 Alembic migration 和当前实例身份切换另波，不能把 fixture 当正式迁移。

## 门和停止规则

1. RED 基线已是 `DID NOT RAISE InsufficientPrivilege`，exit1；先只加隔离 ACL fixture 使普通 runtime 拒绝，核角色、RLS 和依赖可访问性。
2. 然后最小连接实现和原 Resolver 正向测试。独立登录必须确实用 `session_user` 回读；单用超级用户 `SET ROLE` 不算身份验收。任何密码只在随机临时私有文件，不打印到测试输出。
3. 专项、相邻回归、身份/权限复审、verification；仅 m1 精确提交。当前库不写、不读商城源、不启 Host/worker/Provider，不回放旧 Run、不 push。

设计风险：独立 issuer 若继承 `aos_runtime`，会继承该角色对**其他**表的宽权限；本波只证明 Assignee Receipt 单表的直写隔离，后续须把 issuer 的依赖读权列成窄授权并收束五表范围。若无法在不扩大权限的前提下完成原 Resolver 正向，本波不强行制造正向结论，保留 RED 和精确阻断点继续独立任务。
