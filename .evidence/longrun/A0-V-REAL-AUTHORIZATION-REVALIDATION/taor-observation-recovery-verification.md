# TAOR 前序观察恢复验证

2026-09-11；Task A0V-TAOR-OBSERVATION-RECOVERY-20260911；基线 a666d32d。

- 修复前：new_runner 单测失败，`KeyError: step:diagnosis`，证实新工作者跳过成功步骤后丢失上下文。
- 修复后：专项 19 passed；包含一次性完整 PostgreSQL 克隆，通过真实 Task/Plan approval/Run/claim/四阶段 Evidence/complete Owner 保存诊断后，另建 Store/Runner 执行下一步骤。原诊断行完全不变、全程两条 step、只调用方案设计 adapter；无 Provider 调用。
- 负例：缺 observe 引用/证据、重复证据、跨 org/project/run、错误类型、stepRunId/stepKey/hash 漂移、非对象 payload、重复成功及计划外步骤均在 claim 前阻断。后序结果不会提前注入前序 context；adapter 修改恢复字典不影响 timeline 原始证据。
- 累计：新专项 + generation/text-output/agent-run-executor/full-graph/receiver/sources/draft/authority-contracts/authority-store/approval 共 195 passed，7 个既有警告，退出码 0，3.12 秒。测试显式开启 AOS_GROWTH_DRAFT_FULL_GRAPH_TEST=1、AOS_GROWTH_DRAFT_OWNED_CLONE_TEST=1；只由自有模板创建一次性数据库，finally 删除。
- 既有 JDBC 退出清理 closed-stream 日志错误仍出现，未影响退出码；不扩展本波修改。
- git diff --check 通过。未改数据库 schema、主库业务数据、Provider 配置、API 运行版本或 UI；未 push。

方案一致性：读取既有观察 Evidence、复用 canonical hash、按计划顺序恢复、无副本写入；历史观察不是当前授权。实际运行服务尚未重载此代码。没有真实数据或经营计划产物，不声称 A0-V/首链/八场景完成。

下一波：D03 受信工作者绑定与慢调用租约/未知结果处理，连接已实现 GrowthPlanGenerationService；之后真实来源、正式运行配置、首次分析/自然触发、审批后内容续跑及八工作台场景。
