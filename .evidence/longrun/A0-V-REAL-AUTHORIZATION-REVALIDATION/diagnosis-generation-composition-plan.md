# D02 生成执行组合方案

2026-09-11；基线 m1 d3b5f2f5；AOS-000573。按 231-5/231-6 串行真实链施工；不 push，230 L0 挂起。接续 diagnosis-trusted-receiver-plan.md。

## 产品行为

已被正式分配且运行中的 D02 AgentRun，依据当前画像及完整真实来源，通过现有受预算/容量/模型/数据策略控制的 Executor 生成诊断，原文保存后交 DiagnosisReceiver 形成正式诊断。已完成调用只恢复，任何已有 prepared/invoking/unknown/failed 都不自动重发。此次不是创建 AgentRun 或完成真实首链。

## 文件与设计

- 新增 `services/aos-api/aos_api/ecommerce_analyst_diagnosis_service.py` 和对应 `services/aos-api/tests/test_ecommerce_analyst_diagnosis_service.py`。
- 修改 `services/aos-api/aos_api/ecommerce_analyst_diagnosis_receiver.py`，抽出原有当前 Insight/完整来源/声明输入读取为共享函数，供首次生成与新保存复用，保持既有接收语义。
- 补 `ecommerce_analyst_analysis_sources.py` 返回受管 bundle.marking，并在 `ecommerce_analyst_diagnosis_generation.py` 材料合同接收该元数据；旧固定 prompt 不包含它，原请求hash不变。新执行入口同时校验 bundle 与每条正文级别，缺少 bundle 级别拒绝新出域。更新相应来源测试夹具及新增分类测试。
- 命令只接受精确 Insight/source grants 与显式 budget/capacity、版本、attempt 和数据级别；不接受自由 prompt、替代模型或虚构结果。
- 强制显式连接与启用正文留存的执行器。对已有 attempt 先核对全部原命令身份，成功才恢复；首次要求同租户、同 ID、running、精确版本、D02。
- 前置确认012正文表、当前来源、原输入清册、固定完整 prompt，并验证请求分类不能低于任何原文 marking；未知或不支持的 marking 拒绝出域，不能将来源读权限当出域权限。
- 关闭来源事务后调用现有 Executor，不跨网络持锁；Executor 承担现时 route/policy/预算/容量/出域检查，拒绝/未知不得保存诊断。调用返回后再次用当前时间验证来源/恢复；clock 显式传入，并在调用边界复读，不能拿调用前时间给慢调用保鲜。
- 对可变 command/markings 做本次深拷贝，避免异步等待期间调用方修改来源或分类。来源快照后撤销竞争仍由运行策略及接收复验处理，不宣称跨 Provider 的事务原子性。

## 验证与退出

固定请求哈希、事务退出后单调用、分类不降级、同次输入不可被外部修改、调用后时钟刷新、前置失败零调用、已存在状态不重试、未知结果不发布；完整隔离库使用上一波真实表图，从已成功原文恢复诊断且零 Provider。受影响关联回归、方案一致性审查、证据/文件hash与提交。

下一波 D02 TAOR 工作者、D01正式指标/方法来源与三阶段宿主；随后运行配置与真实数据恢复、经营参谋业务计划首链、八工作台真实场景及连续观察。
