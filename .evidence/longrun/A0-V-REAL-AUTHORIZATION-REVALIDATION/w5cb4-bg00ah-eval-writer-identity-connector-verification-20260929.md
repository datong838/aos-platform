# W5CB4 BG-00ah｜Eval writer 独立身份 connector 验证

## 文件与 RED

依据 `w5cb4-bg00ah-eval-writer-identity-connector-plan-20260929.md` 新增 `services/aos-api/aos_api/aip_eval_writer_connection.py` 和 test-only 真 PostgreSQL 测试。未实现时 pytest collection 退出 2（缺模块）；最小实现后首轮 setup 的 `ALTER ROLE ... PASSWORD $1` 不被 PG DDL 接受，修正为 psycopg `sql.Literal` 安全参数组合后专项 6 passed；新增 symlink、额外可达角色与表权限断言后专项 `8 passed`，最终含相邻 Eval reader/sidecar/签名/预览门累计 `43 passed`，退出 0。`compileall -q`、`git diff --check` 退出 0。

## 真隔离数据库与当前禁入

- 仅在 `colima-aos-a0v-test-only` 的 `aos_bg00ad_schema_v2_20260929@a0v_114` 建机制角色：固定 NOLOGIN/NOINHERIT `aos_aip_eval_writer`，专用 LOGIN/NOINHERIT `aos_bg00ah_eval_writer_login`，后者仅能到达前者。随机口令只在测试运行时使用；未打印、未写仓库。测试额外角色 membership 后在 finally 撤回；最终 membership count=1。此角色对 `aip_eval_execution_receipt` INSERT=false，未获得任何正式写表授权。
- connector 只接受固定环境 `AOS_AIP_EVAL_WRITER_CREDENTIAL_FILE` 指向 owner=进程 UID、0600、regular、NOFOLLOW 的绝对路径；JSON 严格 schema/唯一键与固定 role，连接后短事务验 DB identity、LOGIN/NOINHERIT、无 super/bypassrls/createrole/createdb/replication/ADMIN、唯一可达 NOLOGIN role、精确数据库。缺配置返回 None，其余不合格抛错；无 runtime/superuser 回退。
- 当前权威库只读 `aos_current_preview_20260927@a0v_114`：`aos_aip_eval_writer`/test login 角色数 0、正式 Receipt 0、sidecar 0；当前 writer 环境引用未配置、connector_enabled=false。未在当前库创建角色、凭据、迁移或业务行；Skill guard/Host/worker/Provider 仍关闭。

这只证明隔离身份门，不是正式 issuer/Owner/批准或写入授权。下一波 BG-00ai 要复核专属角色的最小 RLS/ACL 策略和同事务 Run/Report/双 Receipt/sidecar 所需权限，先 test-only PG RED 与原子回滚；正式授权来源缺失时仍不落当前库。真实 G2 内容/S3、Gate、自然首链、卸载重装和八工作台待证。
