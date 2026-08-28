# BI-W10-02 AIP 生产组合只读解析验收

- 验收日期：2026-08-28
- 真实租户：`org-org/dev-project`
- 负向租户：`dev-org/dev-project`
- 外部副作用：0
- 真实业务写入：0
- Pipeline 手工运行/补跑/DLQ replay：0

## 实现结果

- 新增 tenant-scoped 只读组合解析器，逐类核验 Logic publication、published SkillTemplate、active SkillBinding、frozen StageTemplate、frozen ResponsibilityPlan 与 Run 级 ProductionContext。
- Case 选择继续独立裁决 `caseCreatable`，并用解析器的精细 `runBlockers` 裁决 `runCreatable`，不再用笼统占位原因覆盖真实差异。
- 多个 published Skill revision、多个 active Binding、过期 readiness、阶段/职责/上下文缺失或引用漂移均失败关闭；不按最大 revision 或展示名猜测生产权威。

## 真实只读回读

`org-org/dev-project`：

- Logic exact refs：D01、D02、D03，共 3 项；
- Skill exact refs：D01 r2、D02 r2；D03 r2/r3/r4 并存，未静默选择；
- Binding exact refs：D01、D02；其 readiness 截止已过期；
- blockers：`AIP_SKILL_REVISION_SELECTION_AMBIGUOUS`、`AIP_SKILL_BINDING_READINESS_STALE`、`AIP_INVESTIGATION_STAGE_TEMPLATE_MISSING`、`AIP_INVESTIGATION_RESPONSIBILITY_PLAN_MISSING`、`AIP_PRODUCTION_CONTEXT_REQUIRES_RUN`；
- `ready=false`。

`dev-org/dev-project`：

- Logic/Skill/Binding exact refs 均为空；
- 返回 tenant-scoped 缺失原因，未串入主租户元数据；
- `ready=false`。

## 验证

- 组合解析器与 Case 选择专项：`13 passed`；
- 全量生意探究、SourceReadiness 与 OpenAPI 累计回归：`412 passed`；
- OpenAPI deterministic check：PASS；
- compileall：PASS；
- git diff check：PASS；
- 页面变化：无，浏览器验收 `N/A`。

## 剩余事实

- 下一切片必须用明确治理规则消除 D03 修订歧义，并补齐生意探究三阶段模板与 frozen 职责方案；不得直接篡改既有生产元数据或用“最新版本”替代权威选择。
- ProductionContext 只能在真实 Case/Run 生命周期中形成，不在预检阶段创建占位记录。
- P07/P08 SourceReadiness 仍等待下一自然窗口，代码与测试 GREEN 不替代 `12/12 READY`。
