# P6D · 模型运行链与受控试聊门验收

## 结论

- 状态：`CODE_TEST_BROWSER_GREEN / CONTROLLED_TRIAL_DISABLED_BY_EXACT_GATE`。
- 范围：`AIP-P6-110`～`AIP-P6-113`。
- 边界：未调用 Provider，未读取凭据正文，未修改真实经营数据，未切换生产路由，未迁移，未发布。

## 实现与权威

- 服务端按每条 canonical route 生成固定六节点链：Provider → SecretRef binding → Policy → Eval → Health → Capacity；顺序、节点数量和受控试聊判定均由严格合同校验。
- 失败节点展示观测截止时间、业务影响、责任入口、复核动作和审计原因码。
- 任务、模型、数字同事、业务逻辑只在共享同一 Usage Receipt 的显式归因存在时关联；当前真实租户有 8 条任务追溯、无显式模型归因，因此没有反向猜测影响对象。
- SecretRef 只显示“已绑定/需同版本健康回执”，API 与页面均不返回引用正文或凭据内容。

## 专项与累计回归

- 后端 runtime API 全文件：`20 passed`。
- 后端 P6 模型治理与 runtime 累计：`40 passed`。
- Web runtime parser + Capacity + W3B 负向交互 + ModelRuntime：`66 passed`（DOM 组使用 jsdom；仅既有 React Router future warning）。
- TypeScript：`tsc --noEmit` GREEN。
- 生产构建：365 modules transformed，GREEN；仅保留既有大 chunk 提示。
- `git diff --check` GREEN。

## 真实租户浏览器验收

- 租户：`org-org/dev-project`，组织显示“栖月汇商贸有限公司”。
- 页面：`/aip/model-runtime`。
- 三条路由均展示六节点链；Provider、Policy、Eval、Capacity 已验证，SecretRef/Health 因同版本新鲜 Health 缺失而显示“需复核”。
- 三个“当前链路不可试聊”按钮均为 disabled，没有发起模型调用。
- 责任入口可展开并跳转 `/aip/model-providers`，返回后状态保持。
- 主层不再显示开发态“阻断/待补齐”；任务技术 ID 收入审计折叠区。
- 浏览器控制台无错误；侧栏完整、可滚动。
- 隔离 canary `dev-org/dev-project` 返回 0 条链、0 条任务追溯、0 条模型影响，未泄露真实租户数据。

## 证据

- `p6d-browser.png`
- `p6d-plan.md`

## 方案一致性与风险复审

- 全链复用现有 Provider、ModelRoute、Policy、Eval、Health、Capacity 与 Usage Receipt authority，没有建立第二真源。
- 同截面未全绿时受控预热/试聊保持关闭，满足 P6-113“不满足时不伪造成功”。
- 当前剩余不是本子包实现缺陷，而是新鲜同版本 Health 运行事实；该事实不会被旧回执、页面状态或测试替代。
