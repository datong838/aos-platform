# BI-W10-02 三阶段、六职责与 Skill 版本选择权威验收

- 验收时间：2026-08-28 18:59 Asia/Shanghai
- 租户：`org-org/dev-project`
- 负向隔离租户：`dev-org/dev-project`
- 外部副作用：0
- Pipeline/Cron/DLQ/Provider 调用：0
- 页面变更：无，浏览器验收 N/A

## 生产元数据回读

- Skill 选择：D01 r2、D02 r2、D03 r4，revision 与 content hash 均由代码权威精确声明；其他 published revision 不参与隐式 latest 选择。
- StageTemplate：`stage-template-0f1211933006443eb325`，revision 2，lifecycle `frozen`，content hash `88d7525c89640e3e020dfc9306a604b46a9ba74cdb11be726d1f0164dd46f5ac`，阶段严格为 `portrait -> diagnosis -> solution-design`。
- ResponsibilityPlan：`responsibility-plan-27275a595e604fd7bdf9`，revision 1，lifecycle `draft`，content hash `73ba7d9880bc06a9bfdc274f71a6e999d0c570b32d94a6ecd9ec51a8d6856ad3`。六职责已绑定六个不同数字同事实例；因 canonical CapabilityBinding readiness 已过期而保持 `blocked/draft`，未伪造 frozen。
- 重入验证：同一 materializer 连续执行两次均返回上述相同 resource id/revision；不会重复创建、重复冻结或改变 freeze Receipt payload。
- 负向租户：无主租户 Logic/Skill/Binding/Stage/Plan 泄漏，保持失败关闭。

## 当前只读组合结论

- 已解析 3 个 Logic exact ref、3 个 Skill exact ref、3 个 SkillBinding exact ref和 1 个 frozen StageTemplate exact ref。
- 当前运行 blocker：`AIP_SKILL_BINDING_READINESS_STALE`、`AIP_INVESTIGATION_RESPONSIBILITY_PLAN_NOT_FROZEN`、`AIP_PRODUCTION_CONTEXT_REQUIRES_RUN`。
- SourceReadiness 截至 `2026-08-28T18:59:34+08:00` 为 `10 ready / 2 failed`，P07/P08 均 failed；本切片没有改写该事实。

## 测试

- authority/composition/stage/responsibility/case selection 专项：`34/34 GREEN`。
- SolutionPack 导出合同专项：`16/16 GREEN`；已有 `growth/harness/live/media/knowledge` 内容均显式落入合法 export 前缀。
- 全量生意探究、SourceReadiness、AIP production contracts、OpenAPI 累计：`710/710 GREEN`。
- `compileall`、`git diff --check`：GREEN。

## 安全边界

本验收只写入 AIP 生产合同元数据及其幂等 Receipt；没有创建真实 BusinessInvestigationCase/Run，没有人工运行 P01-P12，没有 catch-up/replay，没有 Provider 调用、真实业务数据变更、migration 或 release。下一切片必须沿 canonical readiness 求值服务刷新精确依赖，只有真实 READY 后才允许冻结 ResponsibilityPlan。
