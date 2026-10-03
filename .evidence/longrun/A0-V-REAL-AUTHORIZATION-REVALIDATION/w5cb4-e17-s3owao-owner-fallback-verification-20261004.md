# E17-s3o-w-ao｜生产 Capability readiness 默认 owner 回退禁入

按同前缀文件级方案，只移除 `AipCapabilityBindingService()` 未注入独立 Reader 时自动构造 owner `AipBindingReadinessService()` 的路径；不变更显式注入的 Reader/issuer、数据库 schema、白名单或普通 list/get/create。

| 验证 | 新鲜输出 |
| --- | --- |
| RED | 生产路由默认 preview 新负例调用被监测的普通 `AipBindingReadinessService.evaluate_capability`，抛出 `AssertionError: default owner readiness path was used`，exit1。 |
| 最小修复 | 构造器仅保存显式注入的 `readiness_service`；缺 Reader 时 `_require_readiness_service` 抛 `AipAgentRegistryTransitionBlocked`。路由 preview 映射为 HTTP 422，未访问普通 owner readiness。 |
| 邻近回归 | 首轮 32 passed；扩大到原 AIP-6 handoff 时发现旧负例期望到持久层的 `operational` 拒绝，现更早因 Reader 缺席拒绝；只把该负例期望改为 `explicit readiness reader` 并确认绑定仍是 `provisioning`。六文件复跑 43 passed、8项既有 warning，exit0；路由目标1 passed。`py_compile`、目标 `git diff --check` exit0。 |

当前 API 进程尚未重载这份代码。本切片使缺 Reader 的生产 readiness 失败关闭，不产生正式 Reader 角色、issuer、OIDC、八类配置、Binding 或首链；后续还须独立受控配置入口与当前库维护切换，不能把代码门当作当前实例已接线。
