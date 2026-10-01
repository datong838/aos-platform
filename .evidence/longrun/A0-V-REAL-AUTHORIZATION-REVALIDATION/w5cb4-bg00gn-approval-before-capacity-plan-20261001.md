# BG00GN 首生审批先于容量预约

基线 AOS-001054 / m1 46726af5；复习231-5 §§1/4/5/6、447、GM方案与当前Source/Action/Budget/Capacity代码。当前七strong CURRENT、validate GREEN。仅m1串行，不push，不修改真实库或启动Host/Provider。

## 根因与合同

GM首生审批来源含已reserved Capacity，budget intent又只能在容量ACK同事务生成；人工等待因此消耗执行租期。实际租期由capacity pool lease_seconds决定，不能把Quota固定60秒等同实际池租期。不得通过延长旧租期、造budget intent、重试已claim来修复。

复用现有Source准备逻辑增加before_capacity显式阶段：审批前只能来自pending0或精确claimed1的capacity intent、current103、真实queued AgentRun/version1、原Review/Plan/Runtime/配置；执行阶段保持budget intent/current104/running与真实Capacity全部条件。每次现读，不缓存授权。审批来源schema v2绑定原业务输入、精确模型/费用/配额/安装代次，不绑定尚不存在的容量ID和expiresAt；实际预算命令仍必须带真实容量，并独立检查池精确route/model/provider及token覆盖。v1旧批准保留不可变记录，不自动转换或延长，v2重验失败封闭。

## 文件与顺序

1. aos_api/ecommerce_content_budget_command_owner.py：_prepare_sources增加显式before_capacity分支，共享其余来源核验；增加审批阶段选择器；_approved_action可要求精确firstContentReviewKey，防普通旧批准启动容量。
2. aos_api/ecommerce_content_first_action_binding.py：预览/创建/复核使用审批来源选择器；v2 envelope去掉Capacity引用/期限；审批期限仍受15分钟及Quota/Budget期限约束。共享预算来源函数默认必须有容量，只有只读批准核验显式允许审批前来源。
3. aos_api/aip_budget_reservation_store.py：根据原reserve传入的精确预算/价格/调用key要求执行阶段来源，不能因pre-capacity审批允许提前held。
4. aos_api/ecommerce_content_capacity_owner.py：认领前检查正式首生批准；认领同事务再检查。开始执行时在同一外层事务锁住claim/来源/批准，通过TransactionBoundConnectFactory运行现有AgentRunService及CapacityGate；只有外层commit，保持未知结果claimed不重发。原ACK+budget intent事务及Receipt回读保留。
5. tests/aip/test_content_first_action_binding.py、test_content_first_action_binding_pg.py、tests/extension_runtime/test_ecommerce_content_capacity_owner.py与新增test_ecommerce_content_pre_capacity.py：RED覆盖无容量可审批、v2稳定、无批准零claim、执行阶段仍拒缺容量、阶段/claim漂移、同事务占容量及失败回滚。原GM PG来源替身须明确保留证据边界，不宣称完整来源到held。

## 验证与风险

专项及GM累计Action/Budget/Capacity邻接回归，实际PG验证已有存储与事务边界；后续完整合法来源到风险预算held仍必须无来源替身联合验证。纯后端本波无UI，browser不适用。锁顺序、事务绑定、expiry越界、旧批准失效、过期/unknown不重发重点复审。任何不足如实落verification，不称自然首链完成。

本波计划/verification精确入库，Task/Delivery/CAS/Prime/D-waves/448收口。下一波完整来源联合证明及原Action产品路由；不以子测试替代正式首链。

实施补充：既有test_ecommerce_content_budget_command_owner.py的来源fixture增加真实合同字段并参数化审批前阶段，单独TEST Receipt登记；不删生产校验来适配旧fixture。

复审补充：审批前只读核当前唯一精确模型容量池及token quantum，避免已知配置不足消耗claim；实际消费核当前池route/model/provider。容量Gate/AgentRun共享批准事务，外层提交前以clock_timestamp再次核批准有效期；隔离PG测真实预约不可提前可见、异常与批准到期均回滚（AgentRun转换明确用替身，不冒完整联合证明）。
