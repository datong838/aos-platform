# E17-s3h 原签名 Quota 候选读者验证

- 仅扩充 `services/aos-api/tests/aip/test_quota_policy_activation_pg.py` 已有签名 maker/checker→低权 Quota 消费正向测试；审批完成、消费前取基线，原候选读者回 `quota_policies` +1，其他七项/dev-org 不变；同键消费/回读和原精确 active reader 保持。产品代码、SQL、当前真库均未改。
- `python -m pytest -q --disable-warnings .../test_quota_policy_activation_pg.py`：28 passed，退出0，内含 text-only active、直接写、drift、unknown、过期、并发负例。相邻 ModelGovernanceStore + runtime candidate：10 passed，退出0。py_compile、diff check 退出0。
- 新断言在现有已能消费的路径上首次运行即 GREEN，未产生新的 RED；本波是原生产者和候选读者的覆盖补足，不宣称新增产品功能。候选计数不证明当前实例八类齐备、配置绑定、Host 准入或首链。下一波审原 RuntimePolicy/ResponsibilityPlan 有效来源及签名身份。
