# W2-00 R33B 交付消费与 m1 基线合流方案

## 事实基线

- Authority revision：`AOS-000153`。
- 上游精确 Delivery Receipt：`AIP_R33H_P02_HEALTH_CLOSURE`。
- 待消费 m1 revision：`eb0a63cc0c264f93eb116b22982ea409078a4f24`。
- 当前分支：`w2-workshop`；合流前 HEAD：`a79db5163cbcc6ed75d1b0b6a6312903cbf44aec`。
- 正向真实租户只允许 `org-org/dev-project`；`dev-org/dev-project` 仅作负向隔离 canary。

## 本波目标

1. 只读核对上游 Receipt、Authority 与 m1 revision 的精确对应关系。
2. 以非 rebase、非 force 的 merge 将当前 m1 基线带入 `w2-workshop`。
3. 对合流后的 SourceReadiness API、Web SDK、阻断态 UI 与累积契约做回归。
4. 使用内置浏览器验证 Workshop 页面可见状态，不触发真实业务写入或 Provider 副作用。
5. 固化证据、Delivery Receipt 与安全提交，为 m1 后续串行 CAS 提供独立事实。

## 文件级范围

- `.evidence/workshop/2026-08-23-w2-00-r33b-handoff/**`：本波方案与只读验证证据。
- `m1@eb0a63cc0c264f93eb116b22982ea409078a4f24` 合流产生的版本化文件：仅接受上游既有提交内容；若出现冲突则停止并 safe-blocked。
- `services/aos-api/**`、`apps/web/**`：只在合流后测试暴露确定性兼容问题时做最小修复。
- 共享记忆仅新增本 Task/Delivery Receipt；不修改 authority、01/06、Prime 核心投影。

## 明确排除

- 不读取或覆盖 `w1-aip` 未提交工作区。
- 不修改真实业务数据，不执行迁移或发布，不发起 Provider/外部副作用。
- 不 replay 既有 pilot，不自动 retry，不以 2/3 Health 代替 3/3。
- 不改动外部 docs 工作区中未跟踪的 107/112/113/114 方案文件。

## 验证与停止条件

- 合流前使用 merge-tree 预演；出现冲突立即停止。
- 运行 SourceReadiness 后端、Web SDK/UI 专项测试，并运行与 Workshop 入口相关的累计回归。
- 页面使用内置浏览器验收；只读检查真实租户视图与负向 canary 隔离，不执行提交类动作。
- 若 Authority、Lease、分支或上游 Receipt 在执行中漂移，停止状态变更并重新核验。
- Health 仅代表上游 Receipt 的证据截止点；未来真实任务仍须在 task-time 重核 3/3。
