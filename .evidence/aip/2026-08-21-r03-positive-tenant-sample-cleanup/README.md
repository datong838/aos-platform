# R03 · AIP 正向租户样例与假绿清理 EvidencePack

- 波次：`R03 / UX25-03`
- 分支：`w1-aip`
- 开工基线：`09d28c1909dba5058d8dfb55ec759acdeff8c0d7`
- 正向租户：`org-org/dev-project`
- 负向 canary：`dev-org/dev-project`
- 副作用：`NO_MIGRATION / NO_PROVIDER_CALL / NO_SECRET_PAYLOAD_READ / NO_ENDPOINT_DATABASE_WRITE`

## 交付结论

1. Studio 不再预填 `ORD-8821` 示例问题，不再展示 `87%` 虚构评测分数；没有 exact EvalRun 时只显示“未评测”。
2. Studio 复用 R02 canonical operational projection。模型为 Mock/fallback、投影不可用或 `routes.runnable=0` 时，发送按钮失败关闭，禁止调用聊天接口冒充真实试运行。
3. 智能体导入不再预填第三方仓库、路径和欺诈能力；无 exact Scan Receipt 时显示 unknown，后续步骤和“下一步”均失败关闭。
4. 浏览器验收中发现并修正状态语义：门禁拦截显示“受阻”，初始态显示“未开始”，不再误报“导入失败”。
5. Draft 审批台现存 `W-J3 sample chain` 是真实数据库历史样例。本波不以字符串过滤掩盖，也不在 w1-aip 越权写库；迁移至负向 canary/sample namespace 登记为 m1 串行集成数据尾项。

## 验证结果

| 验证 | 结果 |
|---|---|
| R03 targeted Vitest | `4 files / 47 tests passed` |
| Agent Import 最终 targeted | `1 file / 25 tests passed` |
| Web 全量 Vitest | `198 files / 1987 tests passed` |
| `git diff --check` | `GREEN` |
| Vite production build | `BLOCKED_BY_PREEXISTING_TYPESCRIPT_BASELINE` |

构建只剩两个未触碰文件中的既有错误：`ProductionContractsPage.tsx` 缺少 `productionContextRef`，`W1InteractionHonesty.test.tsx` 的 `listObjectTypes` 测试替身类型不匹配。R03 曾引入的字面量窄化错误已修复，构建输出不再包含 R03 文件。

## 浏览器验收

使用 w1-aip 前端 `5174` 与 API `8080`，在 `org-org/dev-project` 验收：

- `/aip/studio`：真实投影 `0/3` 模型路由可派发；输入为空；发送按钮禁用；无 `ORD-8821`、`87%` 或 `mock-llm` 正向展示。
- `/aip/agent-import`：仓库与 Agent 路径为空；状态“未开始”；无 Scan Receipt 时“下一步”禁用；点击“仓库扫描”仍停留 `1/5` 并显示“受阻”；无“仓库可达”假绿。

## 回滚

回滚七个代码/测试文件即可。没有迁移、没有持久化写入、没有 Provider 调用，不需要数据回滚。Draft 历史样例未在本波修改。
