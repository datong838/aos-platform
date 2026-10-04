# E17-s3o-w-ao-b40｜隔离安装与 Registry 撤销锁竞争计划

## 上位方案、现状与问题

- 231-3 的安装启用/停用要求当前签名、权限和头锁持有至提交；BIND-1 要求 Capability Binding exact 依赖、expected-version CAS 与 Receipt。b37 同事务 Reader 目前先选 active 安装、再复用原 Registry advisory `(228,1)` 重验，但**没有安装行共享锁**；b39 仅证明低权 SELECT/RLS 可读。
- 原 `PostgresInstallationStore.lock_for_cas/transition` 对安装行 `FOR UPDATE`；`load_active_baseline_in_transaction` 用 `FOR SHARE`。原 `PostgresRegistryStore.transition_version` 先取 `(228,1)`、再锁版本行；`RuntimeReleaseRevalidator` 也取 `(228,1)`。现有 Capability active 的写事务只重算独立连接 readiness，再 UPDATE/Receipt；签名来源尚未进入最终事务。
- 本波只在可销毁 full-schema/OCI 的 test-only Growth1.13 active 安装验证底层锁/低权权限；不修改当前真实库、不将证据视为发行许可。若只靠 SELECT 与 RLS 无法 `FOR SHARE`，先保留失败，再在 test-only 精确授必要权限，检查不可同时授无界 DML。

## 文件级步骤与判据

1. 在既有 `services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py` 的 Growth1.13 active 段，复用 b39 disposable 非 owner 角色与八表 SELECT/RLS，先对事务内 Reader 的**显式安装锁选项**写 RED；其返回后另一连接对同一安装行 `FOR UPDATE` 与 Registry `(228,1)` 都须在短 lock_timeout 内受阻，事务释放后均可取得。错租户须空读，角色不能获得 Registry/Binding 写权。
2. 在 `services/aos-api/aos_api/extension_runtime/current_installation_release_evidence.py` 给内部 `_read_unique_active_in_transaction` 加默认关闭的 `lock_installation`：仅调用方 SERIALIZABLE、可写事务可启；选择唯一 candidate 后按租户和 id `FOR SHARE` 锁安装行，锁后重验 active=current，再沿原精确签名/Registry/字节重验取得 advisory `(228,1)`。公开只读包装不启锁、不改变返回的 `EVIDENCE_ONLY_NO_START`，错误/权限不足失败关闭。这只增加最终事务可复用原语，不把它接入 Capability active。
3. 先无选项 RED，再最小实现；串行 full-schema 专项、当前只读 Reader 与相邻 AIP 回归，确认 cleanup、静态检查和方案一致。底层互斥不能替代原生产 transition 的撤销/换代并发或 Binding CAS/Receipt；保留 b34/b37 strict xfail。

## 安全边界与下一步

- 正式 issuer/Reader 登录当前仍缺；b40 不生成正式凭据、不迁移当前卷、不启 Host/worker/Provider。`FOR SHARE`/advisory 的底层互斥通过后，还需安装行锁→Registry 锁→签名重验→Binding CAS/Receipt 的最终受限 issuer 原子接线和原 transition 撤销并发测试，才能考虑关闭 xfail。
- 正向只 org-org/dev-project，dev-org 零副作用；不读商城源、不重放旧12 Run、不手工 run_definition、不碰230 L0、不 push。每日提醒单独重启最新栈。
