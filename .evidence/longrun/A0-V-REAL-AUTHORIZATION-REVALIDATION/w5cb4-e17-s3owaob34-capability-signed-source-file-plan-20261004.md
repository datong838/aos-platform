# E17-s3o-w-ao-b34｜Capability 签名来源门定位与 RED

## 上位方案复习与修正

- BIND-1 允许 `CapabilityBinding.create` 在 exact published Catalog 下进入 provisioning；active/runnable 才要求聚合新鲜依赖与运行源。231-2/3 要求运行前签名 Release、Installation active/current、generation/epoch/Owner 最终重验。故不在 create 路由粗暴要求 Growth1.13 active，也不把 Catalog 发布当运行许可。
- 当前 `AipCapabilityBindingService.create` 只查 Catalog id/revision/hash/lifecycle，符合 provisioning 边界；`AipBindingReadinessService.evaluate_capability` 查 published 与 Model/Route/Eval/License/Data/Tool/Budget，但未读 Catalog `source_ref` 与当前签名 Installation。`update→active` 会重算该 readiness，因此真实风险位置是 active/运行前来源验证，不是 create。
- 当前正式 Growth1.13/Owner 缺、当前库只读，不能通过 test-only signer/身份生成正向。b33 已证明 s3e–s3i 隔离配置生产者完成，不能重跑当真实发行。

## 文件级步骤

1. 在 `services/aos-api/tests/aip/test_aip_binding_readiness_service.py` 用现有 authority 测试夹具做最小 RED：Catalog published、其他依赖可用但签名来源不存在/失效时，`evaluate_capability` 应给来源阻断且不可 active；先确认原实现是否错误地返回 available。别对当前真库写。
2. 拆出可安全落地的 Reader 字段：在同一测试文件要求 `PostgresBindingDependencyAuthority.capability()` 回读 Catalog 原 `source_ref`，原 SQL 缺此列应 RED；仅在 `services/aos-api/aos_api/aip_binding_readiness_service.py` 原 SELECT 增该列，不改变现有 readiness 判定或正常调用。它只是证据传递，不是 signed release 校验。
3. 只有明确 Reader/生产权限与当前签名 release 判据后才加 exact source gate；若仅加一个可被测试伪造的布尔值会放大假权威，停止在 RED 与合同，不做不安全补丁。保留普通非正式调用兼容；runtime gate 仍独立最终重验。
4. 专项/相邻回归、方案一致性复审、verification；精确 m1 提交并登记完整来源门仍缺。原库只读、Host/worker/Provider关；收到每日提醒独立再做一次最新栈重启。

硬边界：`org-org/dev-project`唯一正向，`dev-org`零副作用，不读商城源、不回放旧12 Run、不手工 Run、不碰230 L0、不 push。
