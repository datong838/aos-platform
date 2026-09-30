# W5CB4 BG00dj｜growth 1.12 隔离 build/qualification/sign 验证

## 方案、RED、失败复盘

先读 231-2、current builder/signer、BG00di 候选，写独立文件级方案。新 profile/signer RED exit 1，6 errors（脚本不存在）；签名资格 receipt 负例 RED exit 1，1 failed（资格门不存在）。实现后新旧 profile/signer 12 passed。

新候选首次隔离 build exit 0 `BUILD_GREEN`；qualification exit 1 于 `ReleasePolicy._assert_release_evidence`，因 1.12.0 缺本版 `bundle-evals.json`。按方案补充实际 38 passed 的 source/contract eval，`runtimeReadiness=blocked`，保留失败现场，不复用 1.11.0 eval；使用全新 `r2` 目录重新 build/qualification/sign。

## r2 原始可复核证据

- 候选 1.12.0 source hash `5175c24ccd010428e5c4cf54c6cee9d92ec8ccb4cc9ccb92a5c88a55288e0017`；1.11.0 原树 hash `47b1b5ff4093ba76606b8a54867dde312d94ee3565eff959087225b4157e6b4c` 未变。
- `scripts/build_ecommerce_growth_1_12_candidates.py` 无副作用 preflight exit 0：4 包、8 模块、15 操作，growth 精确 1.12.0。
- 隔离引擎 `colima-aos-extension`，registry port 18438；r2 build exit 0，receipt `/Users/ddt/work/projects/ai_agent/.aos-growth-112-build-receipt-r2-20260930.json`：`BUILD_GREEN`，output tree `sha256:91f6b050461d17c89d95e9642f51fb72713766938d6d443df789e05ab4166466`。
- r2 qualification exit 0，receipt `/Users/ddt/work/projects/ai_agent/.aos-growth-112-qualification-receipt-r2-20260930.json`：`QUALIFICATION_GREEN`，同一 output tree，3 runtime sessions 均 released，2048 次 heartbeat，growth read probe 标记 `qualification-fixture-only/executionAllowed=false`，7 类篡改负例被拒。
- 本地隔离 signer 要求上述 exact qualification receipt；r2 sign exit 0，receipt `/Users/ddt/work/projects/ai_agent/.aos-growth-112-signing-receipt-r2-20260930.json`：`SIGNED_TREE_GREEN`，签名树 `sha256:5ceecd5b9bb311bd98670fcbdd16806080fac1ec2a889115e712527d1b684e74`。独立新进程 `ManifestLoader` + `ReleasePolicy` 回读四包均 `SIGNED_POLICY_OK`，BI 模板原字节 SHA256 `76036401433342f95328c43ecbcb618deb3c6adba335532b6bfc11af896d0f3b`。
- r2 build/qualification/sign receipts 的 Registry publish、installation mutation、Provider invocation、external publication 四项均 0。最终新旧候选/build/sign/resolver 相关回归 exit 0，44 passed、7 warnings；`py_compile`、`git diff --check` exit 0。
- 当前正式 Host 预检仍 exit 2 `SAFE_BLOCKED/CREDENTIAL_FILE_REQUIRED`。当前 DB/安装/旧签名树未改，Host/worker/Provider 未启；无 browser-pilot 截图。

## 结论与下波

证明 **本地隔离 1.12.0 四包构建、资格检查和开发签名链**，不代表当前正式批准/身份/安装/业务运行。`bundle-evals.json` 的 runtimeReadiness 仍 blocked。BG00dk 复习正式 trust root、签名升级与 Registry/安装不可变迁移合同，先对当前库和签名 receipt 只读盘点，设计备份+克隆全链+零执行窗口；三身份、Owner、八配置仍要独立授权来源。不得把本地签名树替换到当前实例。
