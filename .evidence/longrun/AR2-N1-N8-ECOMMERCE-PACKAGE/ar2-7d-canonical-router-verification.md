# AR2-7D D3 Canonical Router 验证

2026-09-09，基线 `m1@4b6d2e5f`；m1 串行、不 push、230 L0 挂起。本切片只闭合非 HTTP 唯一派发，不宣称整波 7D GREEN，不前推 `AOS-000571`。

- TDD：缺模块 `ModuleNotFoundError` 为 RED；最小实现后专项 5 passed，宿主端口邻接 25 passed，合计 30 passed / 5.74s（`--noconftest`）。
- 覆盖：只读签发 DispatchRef 后再 HostPort `FOR UPDATE` 提交；未知 operation 不碰库；registration-only 仍 `AR2_7D_RUNTIME_WIRING_REQUIRED`；fence 在签发阶段拒绝且不加锁；legacy 无兼容服务拒绝。
- `python -m compileall` 与 `git diff --check` 通过。
- 文件 SHA-256：router `285b8ab3ec205a2c453cdbab37d98a48e39d12e930105b066d8f54935f8afdef`；test `5979deac731908a9aafa5938373ee4df785ec627f835af096798ed1565f4997b`；plan `e594eed2c560e2789eff744a411ed344d88a9acd93f5dc6c515502ae46bf8a3e`。
- 生产 `build_registration_only_ecommerce_growth_registry()` 未改；无 HTTP 挂载、无 runtime factory、无 Provider/Secret/真实经营写。
- 下一步：`routers/ecommerce_growth_dispatch.py` 与旧经营参谋 URL 单写别名；九项 runtime registry 仍待 HostServices 齐备。
