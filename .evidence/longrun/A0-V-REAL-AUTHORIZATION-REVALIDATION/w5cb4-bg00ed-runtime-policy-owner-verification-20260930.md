# W5CB4 BG00ED｜RuntimePolicy Owner 与配置消费合同核验

## 路径复核

按本波 plan 复习 231 主计划/231-1/231-9 与栖月汇技术方案。生产写入由 `aip_model_runtime.py:484` 的 `POST /v1/aip/model-runtime/policies` 进入 `AipModelRuntimeStore.publish_policy`；后者核 network、egress、data、quota、budget-policy 精确当前依赖，再交 `_publish` 做 tenant、hash、head CAS、递增 revision、幂等 Receipt。当前候选读取只列 active 且非 kill；配置消费在 `aip_runtime_configuration_sources.read_current_runtime_policy_ref` 重核当前 exact ref 和五类依赖。BG00EC 的“未找到 writer”已在 m1@38e94682 和文档清单更正。

路由目前仅 `require_principal`，未看到 policy 专属写角色门。现有产品合同尚未明确该端点的最小角色与 checker 语义；本波记录为权限设计缺口，不以任意角色集合修改线上行为，也不拿此端点向当前库写入。

## 测试与 RED

| 命令/核验 | 退出码与结果 |
| --- | --- |
| `services/aos-api/.venv/bin/pytest -q services/aos-api/tests/aip/test_aip7_model_runtime_store.py services/aos-api/tests/aip/test_aip_model_runtime_api.py services/aos-api/tests/extension_runtime/test_configuration_source_catalog.py` | 1；1 failed、22 passed、11 skipped。唯一失败是旧 `test_store_persists_exact_chain_replays_receipt_and_isolates_tenant` 在测试辅助函数直接插入 active NetworkPolicy，被 a0v_116 DB trigger 拒绝 `NETWORK_ACTIVATION_CONSUMPTION_REQUIRED`；没有绕过门。 |
| 同三文件 `-k 'not test_store_persists_exact_chain_replays_receipt_and_isolates_tenant'` | 0；22 passed、11 skipped、1 deselected。只表示其余现有合同通过，不充当完整 GREEN。 |
| `get_dsn()` 仅输出 host/port/db/user 身份 | 0；测试指向 `127.0.0.1:5433/aos_meta`，容器 `aos-a0v-test-pg`；不是当前权威库 `aos_current_preview_20260927`。 |

## 裁决与下波

本波无生产代码或当前库写入。RuntimePolicy writer 已存在，阻断点是当前正式依赖与签发；active NetworkPolicy 仍无原子审批消费路径，a0v_116 数据库门有效。不能修改测试为直接绕过 trigger，也不能把 22 passed 当成正式首链。下一波 BG00EE 先为 active NetworkPolicy 原子审批消费写精确产品/技术合同，明确 checker、权限、Receipt、UNKNOWN 与克隆隔离；先 RED 后最小实现、专项/累计、隔离 PG。旧测试按新合法签发路径改造，当前真库继续只读。

Host/worker/Provider 关闭，不读商城源、不写 dev-org、不重放旧 12 Run、不手工 run_definition、不 push，230 L0 挂起。
