# AR2-7D D4 生产 runtime registry（fail-closed）

基线 `m1@bf92ff8e`。沿 231-6：新增无参数 `build_runtime_ecommerce_growth_registry()`；九项 HostServices、runtime Store、feedback 与预算依赖缺任一则整体 `AR2_7D_RUNTIME_WIRING_REQUIRED`，不能返回 5/9 可执行 registry。m1 串行、不 push、不前推 `AOS-000571`。

## 当前事实

已有 HostService：describe / case_put / schedule_put / schedule_trigger，以及 request-only 的 `DataRequirementRequestHostService`。尚无完整 `DataFulfillHostService`、`AnalysisAdvanceHostService`、`ReviewAdvanceHostService`、`ContentGenerateHostService`、`ContentReviewHostService`。因此本切片生产选择器必须继续交出 registration-only。

## 本切片

1. `build_runtime_ecommerce_growth_registry()` 零参数；内部按固定九类名构造 adapter+HostService。
2. 缺类、缺 Store/feedback/预算依赖、adapter 顺序漂移一律 `EcommerceGrowthHostBlocked(AR2_7D_RUNTIME_WIRING_REQUIRED)`。
3. `select_ecommerce_growth_registry()`：runtime 构造成功才启用，否则 registration-only。
4. HTTP `get_canonical_router` 改为走 select，不硬编码 registration-only。
5. 不实现缺失 HostServices，不改旧经营参谋写入口，不切 cutover。

## 文件

- 维护 `services/aos-api/aos_api/ecommerce_growth_host_composition.py`
- 维护 `services/aos-api/aos_api/routers/ecommerce_growth_dispatch.py`
- 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_runtime_registry.py`
