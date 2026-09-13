# BG-02 自然事件消费接线顺序

基线e5d8767e。完成的是保存合同/当前来源与批准/HTTP装配/应用回执；未完成启用、自然消费、Run承接、产品意图UI、真实首链、八场景和持续观察。

1. 来源读取与消费回调必须位于同一个SourceSelectionOwner.run_current_snapshot内部。当前Reader.read完成Owner验证后才把metadata返回给调用者，后续写发生在验证外。先新增run_candidates(conn,policy,actor,run_id,execute)，验证原批次/映射后执行同步回调，再由原Owner做退出检查。read复用此方法，保留元数据合同；不暴露payload、不创建连接/提交/ACK。空观察同样执行回调并受退出核验。
2. 当前策略读取门：精确policy+Case+method+source，不使用旧SchedulePolicy解析器；启用合同独立于save合同，不能凭saved就令approved/enabled为true。启用命令必须明确当前作用域、窗口、原source绑定和真正批准；禁用保留历史记录。
3. 包域负责商品事件时间窗口语义。Host只提供经原批次证明和原Owner校验的metadata，严禁来自任意请求的事件行。需补事件payload完整性校验与只返回必需字段；冻结deadline后按当前数据库时间pending/missed。不得按最大序号推进全局游标，晚提交仍可入选。
4. 消费器在上述回调内锁当前policy/binding/dispatch/epoch，按policy+sourceEventId幂等写Occurrence+outbox；整个事务失败一起回滚。当前实现最多100项，禁止跨事务权限快照。来源run仅用原持久化ingress，不造事件。
5. 后继Run从已提交Occurrence自然承接，幂等Receipt贯穿分析/评审/内容/反馈。先在隔离库全链验证，再新签名候选/真实独立评审/安装配置启用，最后栖月汇真实数据观察。任何代码green不代表业务完成。

本波执行第1项。具体修改services/aos-api/aos_api/ecommerce_product_event_reader.py；新增services/aos-api/tests/extension_runtime/test_product_event_reader_callback.py，保留原PG候选测试。验证callback在Owner退出前、异常外抛、异步拒绝、空观察回调、旧read结果保持。没有新增HTTP接口/业务执行器，不能声称事件已自动消费。
