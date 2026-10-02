# E17-s3o-g｜独立 Assignee 发行连接及窄 ACL 隔离 verification

基线 `m1@9710f1ec`、`AOS-001191`；代码 Alembic head 保持 `a0v_135`。上位/文件级计划见同前缀 plan。本波只在 pytest 的随机 `aos_test_<uuid>_ti4_test`（test-only 5433）执行隔离 DDL；当前原卷 `aos-a0v-recovery-pg-data`/库 `aos_current_preview_20260927` 没有 GRANT、REVOKE、迁移或业务写。

| 检查 | 新鲜结果 |
|---|---|
| 基线 RED | s3of 普通 `aos_runtime` 直插 Assignee Receipt 未报 InsufficientPrivilege，原测试仍 strict xfail；不宣称当前库 ACL 已修。|
| 隔离 ACL | 测试库临时撤 `aos_runtime` 的 Assignee Receipt INSERT/UPDATE/DELETE；普通 `db.connect(org-org/dev-project)` 直插报 `InsufficientPrivilege`。隔离测试完成自动恢复该测试库 ACL 并删除随机 DB。|
| 独立身份正向 | test-only cluster 临时建立 `aos_aip_assignee_issuer` 独立非 owner 登录，随机私有 pgpass；Connector 精确回读 `session_user=current_user=issuer`、数据库、租户 GUC、超时、search_path、非 super/BYPASSRLS/owner、FORCE RLS、issuer SELECT/INSERT 且无 UPDATE/DELETE、普通 runtime 无 INSERT。原 `AipAssigneeResolutionStore.resolve` 用真实 `meta_membership` 读入同租户 Human，持久化 resolved Receipt；普通 runtime 只读对账成功。|
| 负例 | issuer UPDATE/DELETE 拒绝；`dev-org` 仅做零副作用 SELECT canary，不能看到 org-org Receipt；非私有 passfile 在连接前拒绝；再次放宽 runtime INSERT 时 issuer 连接预检拒绝。测试后全局 test-only issuer 角色计数0。|
| 测试/静态 | `pytest -q tests/aip/test_e17_s3of_issuer_acl_pg.py tests/aip/test_w6_01_exact_assignee_resolution.py tests/aip/test_w_l20_assignee_resolution.py --tb=short` → exit0，11 passed/1 xfailed；`py_compile` exit0，目标 diff check exit0。第一次夹具缺 `meta_workspace` 外键父行导致 setup error，补齐隔离数据后重新验证成功。|
| 原实例健康 | 代码头/库 `a0v_135`、签名安装预检 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、runtimeBindings0；备份 SHA256 `e2c3a4b6881e5b4616b92ce42052227d6a20fa34b4310debcda83c939c9e04a0`。代码提交后经原 launchd 服务局部重载 API：PID41397、8080健康/就绪/OpenAPI200；PG18435/Web8434继续监听、Web200，18181 关闭。首次即刻探测 API 为000，待进程就绪后复验200；本波没有完整重启 PG/Web。|

方案/代码复审：新增连接器**默认不接任何 API/Host**，只供显式注入原 Store；没有复制 Resolver 判定、Receipt 哈希或租户算法。Test-only issuer 继承 `aos_runtime` 读依赖，可能同时继承其他表的广泛权限，尚非最终最小权限配置。当前原库 `aos_runtime` 仍可直插 Assignee Receipt，正式受限 OIDC/凭证和主库迁移未完成；严禁将隔离正向当正式身份/六绑定/八配置/Host/首链通过。下一波对 Registry/Skill/Capability/Tool 原发行写路径继续隔离权限切片，再设计正式迁移与零执行切换。
