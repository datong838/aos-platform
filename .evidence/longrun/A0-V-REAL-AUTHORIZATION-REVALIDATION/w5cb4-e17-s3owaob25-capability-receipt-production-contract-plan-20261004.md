# E17-s3o-w-ao-b25｜Capability Receipt 正式迁移与独立发行合同文件级方案

## 上位规则与现时门

- 231-4 要求共享 PostgreSQL 单一权威、非 owner 专用身份、FORCE RLS、受控命令和全局串行迁移；BIND-1 31 要求 tenant scoped、expected-version CAS、幂等 Receipt，且 `org-org/dev-project` 为唯一正向。b24 `m1@5b9abd38` 在完整迁移 test DB 证旧 BEFORE 守卫可被同事务多造 create Receipt 绕过；仅 test-only 数据库派生操作标记 + deferred 双向校验拒绝该反例。
- 代码迁移唯一 head `a0v_135`，当前权威卷/库也为135。`aip6_001` Binding 有 version>=1、tenant PK，`aip6_002` Receipt 有 `(org,project,operation,idempotency_key)` 唯一约束和 FORCE RLS/append-only；当前正式 Capability issuer role0、当前租户 Binding0/Receipt6，运行写门仍503。b17 忠实 ACL 克隆保留 owner/ACL，b15 备份 SHA `e9038a51…f498` 已完整恢复但距本波有时间差，不能替代新切换前一致备份。

## 本波文件级与安全次序

1. 只读复核原表列/触发器/策略/权限、历史 Binding 数量与状态分布、三类 Capability Store 的完整 UPDATE 列差异、已有 b17 ACL 忠实恢复方法和正式 issuer 工厂。精确冻结数据库派生 operation 的分类；如果单靠 status/health 变化不能区分 update/evaluate，列出需要的独立写命令证据，不用调用者可写 GUC 当权威。
2. 在 `services/aos-api/tests/aip/test_e17_s3owaob25_capability_schema_guard_pg.py` 或独立全恢复克隆写 RED：迁移前无专用 marker/双向守卫；真实独立 runtime/issuer 登录下普通 Agent/Skill/Run/Handoff operation 兼容，Capability 无配对/伪 operation/错版/跨租户/撤销/旧事务拒绝；真实旧行迁移必须可读且不得伪造历史回执。test-only SQL 用 b24 反例验证分类、同一 Binding 单事务多写、rollback 与禁用触发器权限。
3. 生产候选变更仅在完整协议和独立恢复证明充分后决定：预计 Alembic `a0v_136`（下游精确 `a0v_135`）最小加列/触发器/专用 role ACL、`RegistryIssuerConnectionFactory` 预检权限收窄、原 Capability 三写正向。迁移一旦加入 m1，代码头高于当前库，必须先执行独立可恢复备份/克隆全链及零执行窗口，不能强行启动或宣称最新。
4. 当前原库继续只读。正式私有 issuer/Reader/OIDC/API非owner身份、Owner/Host、八配置和六 Binding 不因隔离测试自动齐备；缺身份时只阻当前实例，转已有配置来源安全代码项。完成时专项/相邻/累计、适用时最新栈重启和浏览器、方案/代码复审、verification、m1精确提交、01/06/D-waves/Prime同步。

禁止：商城源读取、旧12 Run重放、手工 run_definition、230 L0、dev-org正向写、Host/worker/Provider无正式授权启动、push或清理旧库/卷/备份。Goal 保持 active。
