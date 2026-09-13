# 当前资产与运行阶段分离

2026-09-13T10:01:16.487246+08:00，基线6c4b2b52。
preflight提取身份检查，新增固定validate_current_registration_assets入口，复用安装CAS/active lock/配置授权，只返回runtimeStateValidated=false及executable=false。原target入口完整验证binding revision/ready/enabled/unfenced，返回runtimeStateValidated=true。两个固定入口共用私有实现，HTTP无绕过参数。

RED新增7项因组件缺失失败；GREEN preflight与Owner PG共52通过，7.96秒，7既有警告。测试排空身份仍受config/generation/epoch/installation约束，当前权限拒绝传播，登记ready门仍拒绝排空。新增配置调用测试为编排替身；Owner PG含实际事务/Receipt。没有声称主库完整资产核验已执行。diff-check通过。

主库不变、首次激活仍拒绝。下一波在Owner增加资产+签名组合入口，并在Cutover原exact运行阶段校验之后调用；prepare与commit/resume必须分别验证，rollback保留初始fence=true且不能借此激活。
