# BG-02 事件策略进入既有Owner的实施切片

2026-09-14，基线fa74d1cf。已复核包内ProductEventSchedulePolicy、Host SchedulePut、BusinessInvestigationScheduleStore和biw8_001；仅方案，不已实现。

## 复用与兼容

包内事件策略是唯一领域合同；新Host ProductEventPolicyDraft仅为安装/来源读取上下文，必须与包策略逐字段关联，不能独立批准。SchedulePolicyRevision逻辑资源和既有head/revision/command_receipt三表继续复用。旧once/weekly/on_demand及旧写函数不改，不让旧trigger接受sourceEventId。先完成存储/Owner，再扩展当前schema分派，未完成的操作不得加入RUNTIME_WIRING_PROVEN_OPERATIONS。

事件策略增加新的schema分支，不通过旧enabled字段自报授权。持久存储的事件enabled投影初始false；仅完成当前exact ActionProposal/ApprovalEvent、来源、方法、Case及运行准入后生成event ScheduleBinding。停用/过期/换代始终拒绝新claim。旧策略ID不允许从定时变事件或相反，防止旧批准语义漂移。

## 施工顺序与退出条件

1. 明确存储约束：当前revision表check只有三类policy_kind/cadence；新增迁移在实施前再确认HEAD，暂定039。扩大为独立product_event/event成对组合，保留历史值；不新增第二套策略表。旧函数继续只接受旧schema。新写函数必须同事务锁Case与policy、连续修订、精确prior、同租户来源、原命令幂等及Case schedulePolicyRef更新，拒绝SQL NULL绕过。先隔离PG，主库保持038，迁移租约单独登记。
2. Host存储适配：严格schema分派；事件载荷沿包合同验证，不创建另一套业务状态机。事件读回及Receipt与原key一致；一处失败回滚Case+policy+Receipt。不修改既有定时返回结构。
3. 审批沿现有aip_action_proposal/aip_action_approval_event，action_binding_hash与proposal_hash一致，批准内容绑定caseId/policyId/expected revisions和完整事件策略语义hash。当前时间、当前身份、原来源、方法及安装配置重新核验；批准后的来源替换不得复用。
4. 事件绑定与消费：绑定现有event cadence，Occurrence去重不含policy revision；按原入库run完整事件集合分片，元数据不足以代替完整事件校验。结果与outbox同事务，已过deadline记missed，严禁now延长。消费者实际调用Canonical Router之前须完成当前资格登记，不新增裸常驻脚本。
5. 产品入口、真实当前发布包及Host正式接管后，才执行黄埔0期自然链。真实首链/八场景/观察另有证据，不由迁移或单测关闭。

## 当前文件preHash

| 文件 | SHA-256 |
|---|---|
| services/aos-api/aos_api/ecommerce_business_investigation_schedule.py | 507dc1fb42d545953598c52fa34b9e45bd42267ec79a4f805dbfc6887741f13e |
| services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py | 16c28a59a7aa19fc5bc4b8c23a206ba765af8ab0e6f422912742cf06976b6386 |
| services/aos-api/aos_api/ecommerce_product_event_policy.py | 14fcc9976fa4e8bd0a5aa45db233a49917e26a28237936dbf27398e669b91108 |
| bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_product_event_schedule.py | 07cc9387bee74bcc9f66cdcfead0fb39ca621689058abfb6a408f736285e51ed |
| services/aos-api/alembic/versions/biw8_001_investigation_schedule_policy.py（保持不改） | a66d444b4d982fa1379cc29bdfa6dbbde30aa9a820c6d716efdd525f742bcfc7 |

新增迁移、测试、适配器路径在相应开码片登记；修改包前更新AR2 dynamic-reference实际路径清单。不改历史preHash，不复用主库已完成迁移租约。失败保留现场与备份，不自动降级删除业务历史。
