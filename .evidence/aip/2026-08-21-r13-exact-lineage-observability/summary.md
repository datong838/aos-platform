# R13 exact 深链与可观测 EvidencePack

结论：`GREEN_WITH_WARNINGS`。R13 已将真实 `TaskRun` 的 canonical root、Lineage、Telemetry Span 与 Usage Receipt 串成同一条 exact 深链；警告来自当前真实 Lineage 尚未写入 Telemetry Span，以及 R13 范围外的 Workshop 三项外部阻断。

## 权威验收样本

- 正向租户：`org-org/dev-project`；页面回读：`栖月汇商贸有限公司 / 默认工作区`。
- Root：`task_run/run-af0b0f59e7e44ea499ac`。
- Lineage：`lineage-2dce83d6911926580907fdf9`。
- 权威事件：3 条，类型依次为 `receipt`、`action`、`artifact`。
- Telemetry Span：0 条；页面明确显示“证据缺失，不是业务数量 0”。
- Usage Receipt：2 条，均为 `measured`；`output_token=143`、`input_token=340`。
- 浏览器验收截止点：`2026-08-21T11:19:27Z`。

## 实现收口

- Canonical SDK 新增 `evidenceChain(rootType, rootId)`，只采用服务端 Lineage 回包中的 `lineageId`，无事件时不猜测、不继续读取 Telemetry。
- 决策谱系页只在真实 Lineage 加载成功后提供 exact 可观测深链。
- 可观测页支持 `lineageId + rootType + rootId` 自动读取、返回 exact 谱系、分项缺证说明及读取成功后导出。
- AIP Assist 与 Logic Canvas 只以 exact `TaskRun` ref 进入谱系；缺 ref 时显示阻断原因。
- 旧 Provider history 只有 `trace_id` 时不再伪装成 canonical Lineage 深链。

## 验证

- R13 targeted：5 个测试文件、43 个测试全部通过。
- Web TypeScript：`tsc --noEmit` 通过。
- Web 全量累计回归：198 个测试文件、2006 个测试全部通过。
- `git diff --check`：GREEN。
- 内置浏览器：Lineage 与 Observability 两页验收通过；exact URL、3 个事件、2 条 Usage、Span 缺证语义、返回链接与导出门均正确；console error=0。

## 安全边界

- AgentRun 创建=0、Provider 业务调用=0、外部 Action=0、生产 Action=0、Secret payload read=0、旧 Pilot replay=0、migration=0。
- 未修改 Workshop、m1、authority、01/06 或共享记忆权威。
- 未创建 SourceReadiness 或同-cutoff EvidencePack 第二真源。

## Workshop 外部阻断

- `B5_RECEIPT_NOT_CAS_CONSUMED`：归 m1 串行 CAS。
- `W2_00_SOURCE_READINESS_OWNER_MISSING`：归 Data/Adapter 唯一 owner。
- `W2_00_SAME_CUTOFF_EVIDENCEPACK_MISSING`：归 Data/Adapter。
- 上述三项继续阻断 W2-00B，但不否定 R13 AIP 范围的交付。
