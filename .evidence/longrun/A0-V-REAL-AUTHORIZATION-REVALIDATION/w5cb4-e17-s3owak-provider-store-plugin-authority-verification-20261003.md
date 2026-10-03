# E17-s3o-w-ak：Provider 原 Store 插件批准门验证

## 现时来源与边界

当前 `aos_current_preview_20260927@a0v_135` 在 `org-org/dev-project` 的 ProviderInstance、RegisteredModel、RuntimePolicy、ModelRoute、ProviderHealth、Capacity 全为 0（`BEGIN READ ONLY`，查询退出0）；历史 44/46 方案的 Provider r7 属于旧状态，不能直接成为当前来源。仓内 `agnes-text` 原 `ProviderPluginAuthority.get` 返回批准 revision3、hash `124adf49…f1e3dd0e`、Owner `AOS/FDE`；`dev-org/dev-project` 返回 `provider_plugin_scope_not_approved`。没有探测 Keychain payload、调用 Provider 或补当前租户配置。

## RED、最小实现、回归

原 `AipModelRuntimeStore.publish_provider` 只核 Egress/DataClassification，HTTP router 才核 approved Plugin；隔离 PG 有合法 guard 后，以 `test:plugin` 假 ref 直接调用 Store，RED 为 `DID NOT RAISE ModelRuntimeDependencyBlocked`、1 failed/退出1。

仅在 Store 的 Provider 写入口重用既有 `ProviderPluginAuthority.validate_ref(scope,plugin_ref)`，将拒绝转为原稳定 `ModelRuntimeDependencyBlocked`；其余 Model/Route/Policy、HTTP、DTO、迁移未改。隔离测试先断言假插件拒绝且 Provider/发行 Receipt 都 0，再以仓内批准 `agnes-text@3` exact ref 继续原 Provider/Health/Price/Model/Route/CAS/重放链。

| 验证 | 新鲜结果 |
| --- | --- |
| Provider Store、HTTP API、插件 Authority 相邻 | 34 passed、8 warnings，退出0，90.83s。 |
| `py_compile`、`git diff --check` | 均退出0。 |

复审：新门堵住 API 以外的原 Store 入口，未赋予发布者新权限；它不能证明当前正式 OIDC、独立发行身份、Keychain exact item、网络出境批准或健康/容量存在。当前库未写，Host/worker/Provider继续关闭，首链 pending。新运行代码需在原卷重启后另证。
