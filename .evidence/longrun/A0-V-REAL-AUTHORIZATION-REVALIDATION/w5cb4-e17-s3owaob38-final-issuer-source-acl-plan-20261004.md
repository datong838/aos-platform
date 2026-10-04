# E17-s3o-w-ao-b38｜正式 issuer 最终事务来源 ACL 与撤销锁审计计划

## 上位合同

- 231-2/3/4、BIND-1：Capability published 只支撑 provisioning；激活及调用须在权威事务里复核当前签名安装、精确依赖、撤销、租户和 CAS。b36/b37 Reader 均明确 `EVIDENCE_ONLY_NO_START`；b37 新内部原语只使同事务复核在代码上可调用，尚不授 active/run。
- 当前真实库只读、迁移头135；正式 OIDC/issuer/Host Owner、Growth1.13、八配置/六Binding均不齐。不得借 `aos_app` owner、test-only signer 或高权身份绕过。

## 本波文件级步骤

1. 只读核 `aos_current_preview_20260927` 的 `pg_roles` 和原 `RegistryIssuerConnectionFactory` / `ReadinessReaderConnectionFactory` 所需登录，确认正式角色是否存在、是否有可校验凭据。只输出身份是否存在与 ACL 布尔值，不读取密码或商城源。
2. 从 `current_installation_release_evidence.py`、`load_stored_lock`、`_SNAPSHOT_QUERY`、Registry 撤销与 Installation 激活原事务逐表列最小 SELECT/行锁需求，核现有锁顺序。将 active/current 选择、安装行锁、Registry 全局 advisory 锁和 CAS/Receipt 的顺序作为下一可测试合同；不把只读快照当并发保护。
3. 若当前正式 issuer/reader 根本不存在，停止当前实例激活施工于此；不制造 owner 通过的假 GREEN。只在独立 disposable PG/全恢复克隆上为明确 ACL/并发点做 RED，若当前波无法取得合法非 owner 身份，落盘具体缺口并转下一独立安全代码项。任何当前库权限迁移另波备份+全恢复+零执行窗口。

## 验证边界

- 复核当前 m1/卷/代码与库头/最新栈；验证 `memoryctl` Task/Delivery 和 Prime 同步。只读审计本身不宣称 b34/b37 strict xfail、自然首链或正式 Growth1.13 已完成。
- 本波不改 API/DB schema、当前真实库不写，Host/worker/Provider 关；org-org/dev-project 唯一正向、dev-org 零副作用，不读商城源、不回放旧12 Run、不手工 Run、不碰230 L0、不 push。
