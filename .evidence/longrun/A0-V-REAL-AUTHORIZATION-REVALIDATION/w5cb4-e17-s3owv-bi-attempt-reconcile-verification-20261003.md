# s3o-w-v 第一切片｜BI 原写路至多一次与只读 Receipt 对账

- 基线 AOS `m1@fd049e9f`、Authority `AOS-001234`；依据 231-3/231-9、D-wave s3o-w-v、619 和本波文件级方案。当前真实库只读，公开 BI HTTP 写口仍503。
- RED：新增编排测试首次 `ImportError: cannot import name aip_bi_plan_issuer_service`，exit1。最小实现 `dispatch_bi_issuer_command`：每次先用 619 的外部 JWT 重验；以不含 bearer 的命令 hash、可信 actor、租户、操作 namespace 在受保护目录持久保留一次 attempt；只有首次保留成功才调用原 `SignedBIPlanPreparationService.prepare` 或 `SignedBIPlanActiveRebindService.rebind` 一次。
- 对原方法返回或可能已提交后的异常，均只调用原 actor scoped `SignedBIPlanReceiptReader` / `SignedBIPlanRebindReceiptReader` 回读；同键再次进入仅回读。读者异常/无 Receipt 为 `unresolved`，命令/actor 或 Receipt 绑定冲突为 `conflict`，仅精确安装/ETag/Plan/原准备 Receipt/actor 匹配且原 PlanRevision 已验证才为 `observed`。`observed` 仍保持 `current_admission_verified=False`；绝不自动重发。marker 不保存 bearer。
- 新专项6 passed；命令/OIDC、原 network attempt 与 BI HTTP/原服务相邻合计 `70 passed`、exit0；`py_compile`、`git diff --check` exit0。原 Growth 签名全 schema 测试本轮未设置显式一次性 PG/OCI/签名回执环境，因此 `1 skipped`（exit0），不能列作本轮克隆通过；前波既有克隆证据独立保留。
- 测试中的服务/Reader 双重对象只证明编排与错误分支，不构成正式发行或真实 DB 验收。新模块不接公开 HTTP/IPC，不创建 DB 角色/凭据，不写当前真实库，不启 Host/worker/Provider。只读回读当前 `aos_current_preview_20260927`：栖月汇 `aip_responsibility_plan_head`、`aip_production_contract_receipt`、`extension_runtime_host_assignment`、`extension_runtime_binding` 均0。
- 下一步：受限私有进程/跨 UID peer/0600 凭据和独立非 owner DB 登录接线；在可销毁全 schema 克隆用原签名安装和六 Agent 来源跑实际 prepare/rebind/Receipt 正反、未知结果及恢复。当前真实库迁移仍需新一致备份、克隆全链、零执行窗口；正式 IdP/来源缺失仍只阻断该实例。
