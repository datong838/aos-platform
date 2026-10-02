# E17-s3i 原 RuntimePolicy 候选读者验证

- 仅扩充 `services/aos-api/tests/aip/test_formal_model_configuration_pg.py`：沿用签名 Provider/Egress/Data/Network/Quota/BudgetPolicy 及隔离 Model/Route validated fixture；原 `AipModelRuntimeStore.publish_policy` 发布下一 active、kill switch=false 修订，原候选读者回 `runtime_policies` +1、其他七类/dev-org不变。原 Resolver 仍 blocked/无 selected model，未调用 Provider。
- 新断言首次运行即 GREEN，未形成新 RED；这是已有原 Store 权威路径与候选读者的覆盖补足。`pytest` 指定本文件、runtime candidate、configuration assembly：7 passed/29 skipped，退出0；29项为 assembly 环境条件跳过，不宣称其通过。py_compile、diff check退出0。原 Policy 写前依赖验证保留，生产逻辑未改。
- 当前真库仍只读、八类候选仍0；隔离 Policy 正向不证明正式 Model Eval、Route、安装绑定、Host/worker/Provider 或自然首链。下一波原 ResponsibilityPlan 冻结权威与候选读者，须以真实 ready/依赖和精确 Receipt 验证。
