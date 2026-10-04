# E17-s3o-w-ao-b42｜正式迁移排程与当前栈兼容性审计

## 实时核验

- 文件级方案 `m1@c5e07f06`。只读 `ScriptDirectory.get_heads()` 命令退出0、返回 `['a0v_135']`；当前 `docker --context colima-aos-extension exec aos-a0v-recovery-pg psql -U aos_app -d aos_current_preview_20260927 -Atqc "BEGIN READ ONLY; SELECT version_num FROM alembic_version; SELECT rolname FROM pg_roles WHERE rolname IN ('aos_aip_capability_issuer','aos_aip_binding_readiness_reader') ORDER BY rolname; COMMIT;"` 退出0，仅输出 `a0v_135`，两正式 role 无行。`docker inspect` 退出0，容器 PGDATA 实挂 `aos-a0v-recovery-pg-data`。
- 独立全备 `/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261004-s3owaob25-XaGvdX/current-full.dump` 存在，SHA256 `5614c2e76d4bc4abb3229461d44abb4ffa51749ddfc06f5b5f01ff29dfbbccbc`；b25 记录它已完整恢复到无网络 test-only 容器的新库，源/克隆版本135、有效 ACL 与 RLS 摘要一致。该备份是 06:56 创建，不能替代未来正式切换前**新的**一致备份。

## 方案与代码冲突核查

1. b25 计划拟用唯一下一 Alembic 头 `a0v_136` 承载 Capability operation/Receipt 守卫与 issuer ACL，却实测普通 runtime 可在一事务内把 Binding version 增1并伪造 `evaluate` Receipt；因此当时明确不发生产迁移。b41 又证明受限安装锁函数在 test-only PG 可行，但它也尚无正式身份/迁移。两需求不能各自独立声明 `a0v_136`。
2. `scripts/a0v_current_preview_http.py:_code_schema_head/_require_current_schema` 读取代码唯一迁移头并与当前库版本逐字比较，不匹配报 `PREVIEW_CODE_SCHEMA_DRIFT`。在没有全恢复演练和零执行窗口时先把 136 写入 m1，会让当日最新代码+原权威卷的签名预检拒绝；不能继续声称“最新全量启动 GREEN”。
3. 正确顺序：先用 test-only 恢复克隆关闭 b25 不可伪造 operation/Receipt 合同，再确定单一 136 的边界与 b41 锁函数是否同波纳入；若分波，后者只可排在唯一 136 后为 137。迁移生产提交和当前卷切换必须同一受控窗口，前置新备份、全恢复克隆/权限/旧行兼容/回滚、正式非 owner 凭据及零执行。Host/worker/Provider仍关闭。

## 结果与下波

- 本波是已授权的只读排程审计：无 RED/生产代码/迁移/当前库写，也未重启；不把 b41 test-only 函数当正式安装权。当前正式 issuer/Reader/OIDC/Owner/active 安装、八配置/六 Binding、自然首链缺，b34/b37 strict xfail 保留。
- 下一波优先 b25 的不可伪造 Capability operation 证据：在隔离恢复库先构造真实独立受限登录、普通 runtime 冒充、双 Receipt/状态漂移与回滚 RED，精确冻结迁移协议；独立安全线继续正式锁函数 Owner/EXECUTE/事务调用合同。当前实例缺身份只局部禁入，长期 Goal active、不 push。
