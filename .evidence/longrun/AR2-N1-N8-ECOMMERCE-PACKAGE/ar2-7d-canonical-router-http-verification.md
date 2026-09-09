# AR2-7D D3 HTTP 派发壳验证

2026-09-09，基线 `m1@4919e7e5`；m1 串行、不 push、230 L0 挂起。不宣称整波 7D GREEN，不前推 `AOS-000571`。

- TDD：缺 `ecommerce_growth_dispatch.py` 为 RED；实现后 HTTP 专项 6 passed，宿主端口邻接 25 passed，合计 31 passed / 5.88s。
- 覆盖：正文经 Canonical Router；未知 operation 409 且不调用 Canonical；`AR2_7D_RUNTIME_WIRING_REQUIRED` → 503；权威冲突 409；源码不导入旧写服务；九项 operation 集合不变。
- 默认 factory 仍 registration-only。未改 `ecommerce_business_investigations.py`。
- `compileall` 与 `git diff --check` 通过。
- SHA-256：router `fa56ec73c13e0a1207714ff46066a1c4da980b041361aa48a437ad99a7c7faa8`；test `213476e5fc930904f68df395659fa6c1246ddb944b23fe556fa383d32a789f34`。
- 下一步：旧 `/v1/ecommerce/investigations` 写入口改为 Canonical 别名；`build_runtime_ecommerce_growth_registry()` 仍待九项 HostServices 齐备。
