# E17-s3o-w-ao-b40｜隔离安装与 Registry 撤销锁竞争计划

## 上位方案、现状与问题

- 231-3 的安装启用/停用要求当前签名、权限和头锁持有至提交；BIND-1 要求 Capability Binding exact 依赖、expected-version CAS 与 Receipt。b37 同事务 Reader 目前先选 active 安装、再复用原 Registry advisory `(228,1)` 重验，但**没有安装行共享锁**；b39 仅证明低权 SELECT/RLS 可读。
- 原 `PostgresInstallationStore.lock_for_cas/transition` 对安装行 `FOR UPDATE`；`load_active_baseline_in_transaction` 用 `FOR SHARE`。原 `PostgresRegistryStore.transition_version` 先取 `(228,1)`、再锁版本行；`RuntimeReleaseRevalidator` 也取 `(228,1)`。现有 Capability active 的写事务只重算独立连接 readiness，再 UPDATE/Receipt；签名来源尚未进入最终事务。
- 本波只在可销毁 full-schema/OCI 的 test-only Growth1.13 active 安装验证底层锁/低权权限；不修改当前真实库、不将证据视为发行许可。若只靠 SELECT 与 RLS 无法 `FOR SHARE`，先保留失败，再在 test-only 精确授必要权限，检查不可同时授无界 DML。

## 文件级步骤与判据

1. 在既有 `services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py` 的 Growth1.13 active 段，复用 b39 disposable 非 owner 角色与八表 SELECT/RLS，尝试同租户 exact 安装行 `FOR SHARE`。直接执行 SQL 记录权限判据；错租户须空读，角色不能获得 Registry/Binding 写权。
2. 用两条独立连接/受控线程，在角色共享锁持有期间，让原 owner 对**同一 test-only 安装**尝试 `FOR UPDATE`，以短 lock_timeout 证明其不能跨过，随后释放共享锁并证明 owner 可获得锁。Registry `(228,1)` 同理先由重验事务持有，再令独立撤销者以短 lock_timeout 尝试取得，释放后可取得。测试只验证锁互斥/顺序，不执行正式 revoke/publish，也不写真实库。
3. 对缺权限或锁未阻断先 RED，再做最小 test-only 权限/测试修复；串行 full-schema 专项、当前只读 Reader 与相邻 AIP 回归，确认 cleanup、静态检查和方案一致。若底层锁证明尚不足以排除业务撤销/换代漂移，明确下一波构造原生产 transition 的并发 RED，维持 b34/b37 strict xfail。

## 安全边界与下一步

- 正式 issuer/Reader 登录当前仍缺；b40 不生成正式凭据、不迁移当前卷、不启 Host/worker/Provider。`FOR SHARE`/advisory 的底层互斥通过后，还需安装行锁→Registry 锁→签名重验→Binding CAS/Receipt 的最终受限 issuer 原子接线和原 transition 撤销并发测试，才能考虑关闭 xfail。
- 正向只 org-org/dev-project，dev-org 零副作用；不读商城源、不重放旧12 Run、不手工 run_definition、不碰230 L0、不 push。每日提醒单独重启最新栈。
