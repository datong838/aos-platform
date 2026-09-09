# AR2-7D D3 HTTP 派发壳

基线 `m1@4919e7e5`。沿 231-6：新增 `routers/ecommerce_growth_dispatch.py`，只做认证、权限、DTO 与错误映射，不含领域 SQL，不静态导入旧写服务。m1 串行、不 push、不前推 `AOS-000571`。

## 本切片

1. 九条 POST `/v1/ecommerce-growth/operations/{operation_id}`；operation 必须是固定九项。
2. 租户只从 `Principal` 派生 `TenantScope`；请求正文是 strict JSON object，作为 Canonical Router command。
3. 默认注入 registration-only Canonical Router，生产仍 `AR2_7D_RUNTIME_WIRING_REQUIRED`。
4. `EcommerceGrowthHostBlocked`（含 wiring required）→ 503；未知 operation / fence / legacy → 409；权威漂移冲突 → 409。
5. 挂入现有 `domain_aggregates` workshop 组；不改 `ecommerce_business_investigations.py` 旧写入口（单写别名下一切片）。

## 明确不做

- 不改 bundle.yaml 贡献声明以外的签名制品（当前 bundle 无九条 HTTP path，路径先由宿主 Router 固定）。
- 不启用 runtime registry，不切 cutover，不调用 Provider。

## 文件

- 新增 `services/aos-api/aos_api/routers/ecommerce_growth_dispatch.py`
- 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_dispatch_http.py`
- 维护 `services/aos-api/aos_api/routers/domain_aggregates.py`（只追加一行挂载）
