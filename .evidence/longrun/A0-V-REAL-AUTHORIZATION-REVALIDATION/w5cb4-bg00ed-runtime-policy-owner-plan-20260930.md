# W5CB4 BG00ED｜RuntimePolicy 正式 Owner 与配置消费合同方案

## 上位方案与边界

复习 231 主计划 §A1/L2、231-1 四层边界、231-9 公共 AIP 单写 Owner、栖月汇技术实施方案，以及 BG00EC 当前正式来源核验。当前真库只读；不补手工 RuntimePolicy 行、不启 Host/worker/Provider、不触商城源或旧 Run。

## 文件级定位与 RED 判据

| 文件 | 现状 | 本波动作 |
| --- | --- | --- |
| `services/aos-api/aos_api/aip_model_runtime_store.py` | `publish_policy` 经 network、egress、data、governance 当前依赖校验，再由通用 `_publish` 验 hash、CAS、revision、幂等 Receipt | 核对现有测试覆盖；只有真实缺口才最小改动 |
| `services/aos-api/aos_api/routers/aip_model_runtime.py` | `POST /policies` 需要已认证 Principal、Idempotency-Key、If-Match，actor 由 Principal 覆盖；暂未看到 policy 专属写角色门 | 对照上位角色合同；无明确角色合同不任意收紧线上权限，登记风险 |
| `services/aos-api/aos_api/extension_runtime/configuration_source_catalog.py` 与 `aip_runtime_configuration_sources.py` | 只列 active、非 kill 的候选；配置消费者重新校验 current exact ref 和五类依赖 | 通过专项测试检查候选不等于绑定/授权 |
| `services/aos-api/tests/aip/test_aip7_model_runtime_store.py`、`tests/aip/test_aip_model_runtime_api.py`、`tests/extension_runtime/test_configuration_source_catalog.py` | 既有测试 | 运行专项；若发现可复现缺陷先加 RED，再最小修复与累计回归 |

本波不为“当前候选=0”创建伪数据，也不把克隆测试当正式授权。若现有 Owner 正常、仅当前依赖与签发缺失，则本波以只读诊断、测试和 verification 收口。当前实例只能在正式 signer/checker、依赖、Host 身份等齐备后再走 POST；未知写结果先只读 Receipt 对账。

## 验收

1. 可复核找到生产 writer、路由、五类依赖、幂等 CAS/Receipt 与消费侧 exact current 验证。
2. 专项测试 exit 0，缺当前来源继续 fail-closed；无当前库写入。
3. 明确权限风险和下波最小独立研发项，不声称首链完成。
