# 草稿当前来源读取检查点

2026-09-11，基线d3c9932d，m1串行，无push，230 L0挂起。

- 新增只读growth_plan_sources适配器，Decision/Insight只读取当前head exact revision，并验证租户、标识、payload canonical hash；持有head共享锁至调用事务结束。
- Bundle读取复用ProductionContractStore及其marking/撤销校验；要求frozen、complete、fresh、有底层证据、cutoff处于调用侧明确有效期，任务说明仍为当前冻结exact版本。
- 再查底层Evidence exact/hash、撤销、freshness_at及payload marking，拒绝历史Bundle fresh掩盖后续底层撤销。
- Red：新模块不存在，新测试无法导入。Green：累计80 tests passed，exit0。
- 隔离克隆aos_upgrade_check_f1dc452abade实际运行Decision/Insight两类SQL × 两租户共4次缺失ref读取，均按预期拒绝；无写入并rollback。此验证仅证明这两类查询可执行及缺失拒绝，未证明完整正向来源图。
- 限制：无当前栖月汇来源图、无模型调用、无业务草稿写入；Bundle完整路径当前为单元测试。读取仅提供时点校验，之后的撤销仍需审批/执行重验。max_source_age与markings必须由受信业务配置/授权提供，不能直接信任客户端。
- 下一波：原D03 AgentRun声明输入、SUCCEEDED attempt和已保存Artifact核验，借同事务现有Owner持久保存；正向来源图和重放必须在独有隔离环境验证，不向真实租户灌fixture。
