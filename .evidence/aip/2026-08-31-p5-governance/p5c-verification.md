# P5C 决策谱系验证记录

- 日期：2026-08-31
- 分支：`m1`
- 范围：AIP-P5-082～085
- 权威边界：复用 `DecisionLineage` 与 `/v1/aip/lineage-authority/roots/{root_type}/{root_id}`，未新增第二套谱系事实。

## 实现证据

1. 主流程以最近真实任务运行和最近受控动作选择器替代原始 ID；原始 ID 仅保留在高级定位区。
2. 因果链默认显示中文业务事件、来源、证据质量和发生时间，技术 ID/hash 收入审计详情。
3. 同一 exact `lineageId` 联合读取权威事件、Telemetry Span 与 Usage Receipt，并分别呈现闭环状态。
4. 观测或用量缺失时具名显示“缺少观测证据”“缺少用量凭证”，不以 0 冒充事实。
5. 支持关键词、事件类型筛选，并提供审批台、任务协作、业务逻辑、评测及可观测性深链。

## 自动化验证

- Web TypeScript：通过。
- `DecisionLineagePage.test.tsx` + `aipEvidence/client.test.ts`：16/16 通过。
- `test_aip_lineage_authority_api.py` + `test_aip_lineage_service.py`：8/8 通过。
- 外部业务副作用：0。

## 浏览器边界

当前内置浏览器 surface 无可用实例，本记录不宣称视觉封板；P5F 在浏览器恢复后执行逐页滚动、选择、筛选与深链验收。
