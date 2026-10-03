# E17-s3o-w-al｜正式 Provider 只读核验与 Capability 数据/工具证据撤销门

## Rules 与上位方案
- 231-9：secret 只存引用，真实 Owner/批准/Receipt 后续自然执行；AIP-7 第22号方案：ProviderInstance、Route、Policy、Eval、健康、容量与密钥版本必须 exact，未知失败关闭；BIND-1 第31号方案：Data/Tool/License 是 tenant CapabilityBinding 运行依赖，readiness 缺项不得 available。当前真实库只读，不启 Host/worker/Provider、不读商城源、不重放旧12 Run。
- 当前正式租户 Provider/Model/Route/Policy/Health/Capacity 0；HTTP `providers` 以 OIDC Principal、插件批准和 Store CAS/Receipt 发布，Store 仅保存 `secretRef/version`，未证明当前 Keychain exact item 或健康/容量。旧 r7 与仓内插件批准均不能成为当前实例运行来源。

## 文件级最小切片
- `services/aos-api/aos_api/aip_binding_readiness_service.py`：原 `exact_assets_available` 对 `EvidenceBundleRevision` 只核 hash；表允许 `frozen|withdrawn|superseded`，导致撤销的数据/工具证据可能仍返回可用。原生产 Store 的撤销经 `aip_evidence_bundle_revoke_event` append-only 记录，旧 frozen 行仍可存在；对该 kind 同时要求 frozen 且 exact tuple 无撤销事件。`EvalDatasetRevision` 无 lifecycle 列，保持原 hash 校验。
- `services/aos-api/aos_api/aip_binding_readiness_reader_connection.py`：受限 reader 的精确表名单加原 revoke event；独立登录仍必须只读、租户 RLS、无其他表权限，未授 grant 时身份预检失败关闭。正式当前库 ACL 切换另波。
- `services/aos-api/tests/aip/test_aip_binding_readiness_service.py`：先 RED 证明 withdrawn/superseded 同 hash 与 frozen+exact 撤销事件都拒绝，frozen 未撤销正向；EvalDataset 原路径不变。隔离连接替身，不写当前库。
- `services/aos-api/tests/aip/test_e17_s3owal_evidence_bundle_revoke_pg.py`：conftest 创建并销毁的 `aos_test_*_ti4_test` 内原表正向 frozen、同 exact tuple 撤销后负向和错租户负向，证明真实 SQL/RLS；绝不接当前库。
- 证据目录本 plan/verification；当前真库只读回读，必要时浏览器验收。无 migration、DTO、公共协议更改。

## 验收与风险
先 RED，后最小实现；跑专项及相邻 readiness/独立 reader 测试。若真实 PG 测试无可销毁库，不把当前库作为测试库。检查 SQL、tenant 参数、证据生命周期与方案一致；真实 Provider/Tool 发行身份仍独立阻断，不把安全代码 GREEN 当首链通过。新生产代码提交后按原权威卷 PG→API→Web 最新栈复验。
