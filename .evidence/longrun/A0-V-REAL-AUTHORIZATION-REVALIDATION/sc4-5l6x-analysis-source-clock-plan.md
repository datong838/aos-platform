# SC4-5L6X 分析采用原快照时钟

承接5L6W和snapshot-resume-design.md l6g。Rules同W；保持J原Run、失败Outbox和关闭的事件入口，不在本波进行主库业务写入。目标是消除组源分析依赖事件入库时间的逻辑缺陷，不将本波等同完整组调度或历史任务恢复。

## 产品合同

数据截止是原一致快照读取完成时间；事件入库时间仅描述触发时间，二者不要求相等。若来源确属原组，分析只能使用原组完整微秒时间；同时校验actor及原controlRef/run成员归属，不允许借同一租户的别组时间。组身份、manifest及原时间进入分析准备fingerprint，准备前后变化拒绝。原精确数据路由继续验证Requirement cutoff和组时间一致。

已有无组的历史事件保持原时间解释，不回写原Run/Requirement/Receipt。本波仅为组来源添加明确分支，单源自动入口的提前等待/禁入留Y/Z在调度与Occurrence Owner实现，不能由本波抛一个异常把单源事件大量变成unknown。现有J入口仍关闭，故不得因兼容分支继续打开失败窗口。

## 实现文件

- services/aos-api/aos_api/ecommerce_product_event_analysis_service.py：新增原组读取方法；_phase原source守卫内查询，actor/controlRef/member精确一致；request cutoff取组时钟，稳定快照携带groupId/manifestHash/readStartedAt/readCompletedAt。无组保持旧request。
- services/aos-api/tests/extension_runtime/test_product_event_consumer_pg.py：named单源夹具显式提供无组边界；真实ControlledIngressJournal必须委托生产定位，不整体mock组定位。
- services/aos-api/tests/extension_runtime/test_analysis_snapshot_resume_chain_pg.py：去掉aligned_source；在初始化之前接入已准备的原组journal，读取独立source时钟。仍披露源/安装资产fixture边界，不冒充真实商城验收。
- 专项时间/来源负例与既有bootstrap/data route/natural chain回归；需要扩展生产文件先登记。

## 验收与风险

Red必须证明未对齐时钟时旧分析cutoff不等于组时间，路由不能自然交付。Green保持同一Task/Run/Requirement恢复，exact重放，旧单源测试原语义，跨actor/controlRef拒绝。真实主库旧Run不自动转新cutoff；Y/Z须处理无组来源准入和既有失败任务。完整十二源自然调度、模型建议和八场景仍待后续。
