# P5A 评测目标、回归与费用证据核验

- 分支：`m1`
- authority 基线：`AOS-000437`
- 租户：`org-org/dev-project`
- 外部副作用：0

## 已核验

1. Web 全量 TypeScript 检查：0 诊断。
2. API runtime owner：`RUNTIME_OWNER_EXACT`，`/v1/health` 与 `/v1/ready` 均 GREEN。
3. 真实租户目录：39 个评测套件、40 个 Logic 图、80 个 Skill 修订、6 个数字同事模板、3 个模型目录项。
4. `/v1/evals/{suite_id}/history` 返回精确 `target_id/revision/hash`、运行时间与通过率；首个真实套件有 1 次历史记录。
5. 页面只允许当前内部确定性 Logic 直接运行；Skill、数字同事与模型被列为独立 EvalRun 计划。缺精确版本、usage 或价格权威时保持缺证，不显示虚假费用数字。
6. 回归比较只消费同一 Logic `revision/hash`，不跨版本混算；豁免仍只能来自权威审批。

## 未伪造的缺证

- Vitest 在本次隔离 Node 进程加载 `rollup.darwin-arm64.node` 时被 macOS Team ID 签名隔离拒绝；没有把专项测试写成 GREEN。
- 内置浏览器当前没有可用实例；浏览器视觉与交互证据留待实例恢复后补齐。

## 风险边界

- 未调用 Provider，未执行发布、业务写入或真实外部动作。
- 未改变现有评测引擎、评测事实权威或租户隔离策略。
