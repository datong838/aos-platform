# P5F 浏览器与业务可读性验证记录

## 范围与边界

- 真实租户：`org-org/dev-project`；隔离 canary：`dev-org/dev-project`。
- 浏览器逐页核验评测门控、草稿审批、决策谱系、可观测性和记忆治理。
- 仅执行 GET 型读取、页签切换、选择、滚动及侧栏折叠/展开；未运行评测、创建套件、修改草稿、创建或撤回记忆引用。
- 未调用 Provider、发布、发送、重定价、外部写入或真实业务副作用。

## 浏览器验收

1. 评测门控 `/aip/evals`
   - 完整侧栏、真实租户、39 个评测套件和 40 个评测目标均可读取。
   - “读取全部评测目标”“加载回归历史”“读取最新报告”可工作；执行矩阵与精确 Logic 回归可读。
   - 未触发“运行套件”或“创建基础评测套件”。
2. 草稿审批 `/aip/drafts`
   - 读取到 1 个已结束提案；详情展示业务影响、证据、关闭状态与期限。
   - 未执行审批、关闭或其他状态变更。
3. 决策谱系 `/aip/lineage`
   - 读取到 16 个真实任务运行和 1 个动作候选；选择后精确谱系可读。
   - 权威事件为空时保持可信空，不以示例事件补齐。
4. 可观测性 `/aip/observability`
   - 成功运行的精确谱系可读；零 Telemetry Span 明确呈现为缺失证据。
   - “调用轨迹”“用量凭证”页签可工作，读取到 2 条权威用量凭证。
5. 记忆治理 `/aip/memory-governance`
   - 候选、正式记忆、知识管道均为权威空；六个真实数字同事实例可读。
   - 六个页签、完整侧栏、侧栏折叠/展开和页面滚动均可工作。
   - 业务主阅读层已将管道、依赖、就绪度、记忆引用和效果观察改为中文业务语义；原始原因码仅置于“审计原因码”详情。
   - 空贡献上下文显示“选择后显示”，不再以“未绑定”冒充业务状态。

## 租户隔离

- `org-org/dev-project`：候选 0、正式记忆 0、数字同事 6、知识引用 0。
- `dev-org/dev-project`：候选 0、正式记忆 0、数字同事 0、知识引用 0。
- 两租户 API 回显各自租户；隔离 canary 不可见真实租户的六个数字同事实例。

## 自动化验证

- `MemoryGovernancePage.test.tsx`：13/13 GREEN。
- `pnpm --filter @aos/web exec tsc --noEmit`：GREEN。
- 全量 Web：268/268 test files，2376/2376 tests GREEN。
- Web production build：GREEN；仅保留既有 chunk-size warning。
- 浏览器控制台无 error；仅有 React Router future warning 与本地开发服务调试消息。

## 截图索引

- `p5f-browser/01-evals-full.png`
- `p5f-browser/06-evals-read-actions.png`
- `p5f-browser/02-drafts-detail.png`
- `p5f-browser/03-lineage-loaded.png`
- `p5f-browser/04-observability-usage.png`
- `p5f-browser/05-memory-agents-fixed.png`
- `p5f-browser/05-memory-query-fixed.png`
- `p5f-browser/05-memory-pipelines-fixed.png`
- `p5f-browser/05-memory-readiness-fixed.png`

## 结论

- P5F 浏览器与业务可读性闭环 GREEN。
- 该结论只证明代码、浏览器读取、租户隔离和无副作用验收，不授予真实运行、业务写入、外部副作用或发布权限。
