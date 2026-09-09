# AR2-7D D3 Canonical Router（非 HTTP 派发）

基线 `m1@4b6d2e5f`，沿 231-6 AR2-7D-D3：唯一非 HTTP 派发服务。m1 单人串行；本切片不 push 无关脏树、不前推 `AOS-000571`、不宣称整波 7D GREEN。生产 registry 仍 registration-only。230 L0 挂起。

## 本切片闭合

1. 输入仅为宿主鉴权所得 `TenantScope`、固定九 `operationId`、strict command。
2. 短只读事务从 `extension_operation_dispatch_binding` 按租户+operation 签发完整 DispatchRef；**不含** `FOR UPDATE`。
3. `handler_kind=extension` 只调用 sealed registry 组装的锁定 HostPort；提交事务内仍由 HostPort 重锁 group。
4. `handler_kind=legacy` 且未登记兼容服务时 fail-closed。
5. fence / 未知 operation / registration-only 执行路径稳定拒绝；未知 operation 不碰库。

## 明确不做

- 不新增 HTTP `routers/ecommerce_growth_dispatch.py`、不改 `main.py`。
- 不新增 `build_runtime_ecommerce_growth_registry()`，不局部启用九项 HostServices。
- 不改 cutover / 装卸、不写真实领域 Store、不调用 Provider。
- 不修改 `ec_source_adapter.py` / JDBC 等无关脏文件。

## 文件

- 新增 `services/aos-api/aos_api/ecommerce_growth_canonical_router.py`
- 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_canonical_router.py`

## 验证

专项 pytest 先 RED（缺模块）再 GREEN；邻接 `test_ecommerce_growth_host_ports.py` 保持通过。不推进 authority 整波门。
