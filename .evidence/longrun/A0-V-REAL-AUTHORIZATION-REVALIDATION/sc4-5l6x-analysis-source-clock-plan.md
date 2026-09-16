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

专项负例具体文件：新增 services/aos-api/tests/extension_runtime/test_product_event_analysis_source_clock_pg.py，复用原真实Occurrence/控制Owner夹具，对actor/controlRef错配、精确微秒和组manifest准备血缘进行断言；组读取本身由W原Owner PG覆盖。源/安装依赖仍明确named。

Red已复现：原分析cutoff=2026-09-16T00:34:12Z，而独立快照read_completed_at=00:34:13.312160Z；原断言失败（8.88秒）。未改源时间、未改原精确路由。完整组合fixture在初始化前接入已经准备好的真实原组Journal，去除aligned_source。

兼容性复核：AnalysisStartupEvidence.sourceSnapshotHash保存完整stable快照hash。因此无组分支必须保持旧stable字段集合，不能增加sourceGroup:null后声称兼容。仅确有原组时加入sourceGroup；单源旧request/快照形状保持。新增专项断言覆盖这一点，最终回归必须针对该修订重跑原初始化。

继续核查暴露初始化证据时序缺口：ecommerce_analysis_startup_evidence.py原校验event_at<=cutoff<=Run.created_at，只适用旧单源事件时钟。完整组真实顺序为cutoff<=event_at<=Run.created_at。新增该生产文件到本波范围：有原sourceGroup才使用组时序，无组完整保留旧式；不得一律删除时间校验。组合fixture调整依赖顺序为先原native输入，再创建原事件/Claim/初始化；事件和源各自取真实独立时间，不改既有Occurrence时间、不把两者对齐。补负例验证组截止晚于事件拒绝。

时间顺序专项文件：新增services/aos-api/tests/extension_runtime/test_analysis_group_clock_evidence_pg.py，使用原Case/Run/Claim/Evidence Owner，明确named源组元数据，验证先读快照后发生事件可保存原证据、组截止晚于事件拒绝。组元数据真实性仍由W真实Locator与X完整组链另行验证。

最终时序回归中的夹具身份修正：先组输入后formal初始化使原formal的SET LOCAL SESSION AUTHORIZATION在初始化事务提交时自然失效；后续dispatch拒绝superuser会话，这是原安全检查正确工作。调整data_case从当前formal身份取真实session_user并延续到原分析会话，不删除或mock安全检查。专项7 passed，首个完整链在此身份边界报错；修正后整组重新验证。

## X 最终验收

最终代码回归：32 passed / 557.92秒，日志/tmp/aos-source-clock-final-v2.log。包括组时序正反例、actor/control/run错配、单源旧快照形状、原完整组交付续跑、依据撤销、自然Outbox消费、结果未知后的进程重建零新增、原初始化/启动证据回归。git diff --check通过。仅隔离完整PG，安装资产/远程源/Provider仍有named边界；主库J原Run和失败Outbox未改变，未声称真实经营首链完成。

生产最小变化仅analysis service的原组时钟/来源核验和startup evidence的组时序分支；无组request和stable字段保持旧合同。下一波自动进入Y1原子完整组调度领取，具体完整设计已加入原snapshot-resume-design.md及D-waves。主库当前仍a0v_061，当前API/Host尚未加载本波代码，后续升级/重载必须另有新鲜证据。
