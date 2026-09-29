# W5CB4 BG-00bb｜其他 active 策略审批路径审查

复习 231/231-9、BG-00ba 的新 active 禁入后，只读核对 Egress、数据分类、模型配额、模型预算策略的合同、Store/Router 和测试依赖。找可独立修复的最小安全门；不得用非空审批字符串、历史 active 测试或当前空候选证明正式批准。当前库只读；Host/worker/Provider关闭，不读商城源、旧 Run、230 L0。

文件级入口：`aip_runtime_guard_policy_contracts.py`、`aip_runtime_guard_policy_store.py`、`routers/aip_runtime_guard_policies.py`；`aip_model_governance_policy_contracts.py`、`aip_model_governance_policy_store.py`、`routers/aip_model_governance_policies.py`；必要时只读枚举现有测试调用点。若改动会同时改变多条正常依赖，先拆单一路径并立 RED，保留旧记录读取与草稿/幂等语义。
