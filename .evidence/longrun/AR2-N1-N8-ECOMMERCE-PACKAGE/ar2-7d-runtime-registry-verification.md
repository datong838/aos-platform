# AR2-7D D4 runtime registry 验证

2026-09-09，基线 `m1@bf92ff8e`；m1 串行、不 push、230 L0 挂起。不宣称整波 7D GREEN，不前推 `AOS-000571`。

- TDD：缺 `build_runtime_ecommerce_growth_registry` 为 RED；实现后专项 5 passed。邻接 canonical router / HTTP / host ports / runtime adapters 合计 57 passed / 5.75s。
- 当前 `build_runtime_ecommerce_growth_registry()` 因缺少完整 `DataFulfillHostService` 与 analysis/review/content HostServices 而 `AR2_7D_RUNTIME_WIRING_REQUIRED`。`select_ecommerce_growth_registry()` 因此仍返回 registration-only。
- HTTP `get_canonical_router` 改为走 select；零参数 factory，monkeypatch 九项齐备时可构造 exact 九 operation。
- `compileall` 与 `git diff --check` 通过。
- SHA-256：composition `ecd5a490ea1049d5fd1a2e1d3060d6e5a60b94e1f9439d3367c1daf0167d172e`；HTTP router `38bee72304c3eab367314c5986c69ebeeb6daa232fc6e16605f1e3a560fe54ed`；test `7d97ce5fd0110988c6daeb942273c4d55f1fff0fbed0d4b050e9f268b4f262f0`。
- 下一步：补齐完整 DataFulfill 与 analysis/review/content HostServices；未齐备前禁止旧经营参谋写入口切 Canonical。
