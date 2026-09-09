# AR2-7D DataFulfillHostService（请求 + 绑定）

基线 `m1@a0d4060b`。生产 registry 仍会因 analysis/review/content 缺项 fail-closed。本切片只补齐 `ecommerce_growth_data_fulfill` 的命名 HostService：请求委托现有 request-only 宿主；绑定走 `DataFulfillmentStore`，不把客户端 `qualityScore` 写入 Receipt。不 push，不前推 `AOS-000571`。

## 文件

- 维护 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`
- 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_data_fulfill_host.py`
