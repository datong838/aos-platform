# 登记当前权威同事务复用

2026-09-13T09:42:45.599550+08:00；基线33a1787d。
FirstDispatchRegistrationService新增validate_current_authority_in_transaction，register复用原四来源/签名同事务核验；不另开连接、不切角色、不写登记、不提交。要求INTRANS、SERIALIZABLE、aos_runtime，并复用角色/RLS/租户检查。返回requestHash及非执行权标志。

RED新4测试因方法不存在失败。新增真实RLS检查后发现原Owner编排fixture的最小runtime表未启RLS；仅测试夹具补ENABLE/FORCE与租户policy，生产门禁未放松。最终Owner PG、HTTP、preflight、qualification共80通过（12.70秒），18框架/既有模型警告；外部拥有事务backend pid/tx一致且零登记，wrong role/scope/isolation拒绝。当前预检与签名节点在Owner PG中仍是编排替身，不冒充完整真实依赖。

清册1819/158/93五类错误为空，diff-check通过。主库未部署，新方法尚未接入Cutover。下一波在锁内读取exact登记Receipt、核对固定九项来源并调用此方法；还必须处理commit中draining状态下的当前配置重验与未激活撤销，不能提前移除首次激活拒绝。
