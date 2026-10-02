# GW-b-2c2c1b3c2b｜1.13 本地签名与当前来源只读审计

2026-10-02 10:01 CST；基线 `aos-platform/m1 d84a6d7f`、Authority `AOS-001118`。复习 231-2 签名/OCI 供应链、231-5 §9 已接受阶段来源、D-waves c2b 与原 1.12 signer。当前 1.13 r2 仓外 build/qualification 同树 hash `sha256:e46f9bd2…718ecaf`；资格使用短效测试签名，尚无持久签名。

## 文件级与执行计划

1. 新 `scripts/sign_ecommerce_growth_1_13_candidates.py`：复用原独立 signer，仅把 profile 指向 1.13、使用独立本地 keyId。签名前严格要求 r2 build 与 qualification Receipt 的 exact 路径/hash、`QUALIFICATION_GREEN`、四包版本、七篡改拒绝和零作用；state/output 不存在且仓外。不得用旧 1.12 key 或改其签名树。
2. 新 `services/aos-api/tests/extension_runtime/test_sign_ecommerce_growth_1_13_candidates.py`：先 RED profile 缺失；验证新版本/key、错误或缺资格拒绝、已有 state 不覆盖，历史 1.12 profile 不变。后用 r2 exact Receipt 于 `aos-recovery` 独立 0700/0600 状态目录创建本地测试签名，按原 TrustRoot/ManifestLoader/ReleasePolicy 回读四包 exact content hash 与 image/config digest、有效期/撤销状态；输出仅测试来源，不发布当前目录。
3. 同一波只读查询当前权威 `aos_current_preview_20260927`，事务 `read_only=true` 且先核数据库名/卷/`a0v_118`；调用原 `read_candidates` 取八类当前配置计数，核 `extension_runtime_host_identity/assignment`、Growth 1.13 published/installation、原注册 Owner 可否合法解析及三身份凭据引用。只报告行数和门禁，不输出密码/Token、商城源数据；无正式来源继续实例禁入。

## 退出门

专项与相邻测试、签名 Receipt 和源树 hash/OCI index 一致、当前配置/Owner 只读结果、复审与证据。不得把本地测试 key 加入当前正式信任根，也不得创建正式身份/人工 Run。当前 DB 迁移与全面重启仍走独立安全波；Host/worker/Provider 关闭。
