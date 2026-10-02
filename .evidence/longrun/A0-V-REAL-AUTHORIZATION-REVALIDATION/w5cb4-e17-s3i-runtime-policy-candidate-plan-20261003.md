# E17-s3i 原 RuntimePolicy 配置候选方案

- 231首链须当前模型路由和策略。原 `AipModelRuntimeStore.publish_policy` 在写前核当前 Network/Egress/Data/Quota/BudgetPolicy 精确依赖；候选读者只计 head 当前 active 且 kill switch=false。现有隔离 `test_formal_model_configuration_pg.py` 用正式签名来源构造 validated Policy、Model/Route，但 Eval/Health 缺失，不能自然执行。
- 本波仅在该隔离 fixture 增加独立测试：取原 validated Policy，改成下一修订 active、kill switch=false，重算 canonical hash，经原 Store `publish_policy`；核原候选读者 RuntimePolicy +1、其他七类/dev-org 不变；原 Model/Route 仍因 Eval/Health 禁入。先 RED 断言最小权限/依赖链，失败时仅修测试前提，不改产品门禁。
- 具体文件 `services/aos-api/tests/aip/test_formal_model_configuration_pg.py`；相邻 RuntimePolicy/候选测试、py_compile/diff check、verification/精确提交/上下文。ResponsibilityPlan 冻结为下个独立波。当前真库只读，Host/worker/Provider关。
