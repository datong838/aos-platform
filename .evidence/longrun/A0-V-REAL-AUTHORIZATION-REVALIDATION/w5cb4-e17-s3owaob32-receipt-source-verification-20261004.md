# E17-s3o-w-ao-b32｜Capability create Receipt 来源配对验证

## 现场与方案

- 按 b32 文件级方案与 231-2/3/4、BIND-1 施工。`AOS_BUNDLE_ROOT` 指向的 signed-bundles 中 Growth 子目录只有 `1.11.0`；原库 Installation approved3/active NULL 的 b31 只读事实未变。当前只读 SQL：`a0v_135`、CapabilityBinding0、RegistryReceipt6、Host assignment0/revision0、runtime binding0。找不到可用的当前 Growth1.13 签名 release/Owner 事实，未用仓外历史目录替代权威。

## RED、最小改动与回归

- 原 disposable PG helper 的 create Receipt 把 Binding id 误当 Capability source id；先按 b31 生产 Service 的形状改为 published Catalog id/revision，再加错 id、错 revision、缺 revision 三个独立 issuer 同事务负例。原 deferred guard 只检查 source type，目标测试 exit1：`Failed: DID NOT RAISE InsufficientPrivilege`（第一个错 id）。
- 同一 test-only 文件 `services/aos-api/tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py` 的 receipt guard 只加 create 来源 ID/revision 与 Binding `capability_ref` 配对。目标 `1 passed, 1 deselected`；六文件相邻 `33 passed, 1 deselected, 1 xfailed`，exit0；`py_compile`、`git diff --check` exit0。xfailed 是共享 Receipt 正式 operation/session guard 既有缺口；deselected 是 a0v_135 下旧降级测试。
- 未更改生产 SQL/API、当前库/安装/签名状态。b30 published/hash 约束仍仅在 disposable PG；本波配对不证明真实签名 Growth1.13、OCI digest/trust、Installation generation 或 Host Owner。正式迁移和当前实例写门继续禁入；普通共享 Receipt 保持正向。`bda00146` 新生产代码尚未由每日最新栈重启加载。

## 复审与下一入口

- 方案和代码一致：唯一代码改动为一次性完整迁移 test DB 的 Receipt 来源配对；当前真实库没有 DDL。下一波独立核 signed Growth1.13 生产者、release/OCI/trust/Owner 和当前安装代次合同；缺正式身份时继续已授权的配置/绑定独立代码切片。
- `org-org/dev-project` 唯一正向、`dev-org` 零副作用；Host/worker/Provider关，不读商城源、不回放旧12 Run、不手工run_definition、不碰230 L0、不push。
