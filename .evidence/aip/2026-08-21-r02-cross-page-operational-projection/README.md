# R02 · AIP 跨页单一运行投影 EvidencePack

- 波次：`R02 / UX25-02`
- 分支：`w1-aip`
- 开工基线：`b5562f3d7ef68b3895afdae23e1b08299bf7743a`
- 正向租户：`org-org/dev-project`
- 负向 canary：`dev-org/dev-project`
- 数据与副作用：`NO_MIGRATION / NO_PROVIDER_CALL / NO_SECRET_PAYLOAD_READ / NO_ENDPOINT_DATABASE_WRITE`

## 交付结论

1. 新增只读 `GET /v1/aip/operational-projection`，从现有 Agent、Capability、Tool、Eval 与 Model Runtime canonical authority 聚合单一快照，不建立第二写模型。
2. DTO 同时在服务端与前端强制 `defined >= bound >= enabled >= runnable`，并校验租户、时间、哈希、总就绪态与 blocker 一致性；未知或非法载荷失败关闭。
3. Studio、Tools、Maturity、Evals、Agent Registry、Capability、Model Runtime 七页消费同一共享状态条；加载期显示“读取中”，失败显示“不可用”，不把未知投影为 0。
4. 当前真实快照诚实显示：数字同事 `0/6`、专业能力 `0/10`、工具 `0/22`、Eval `6/6`、模型路由 `0/3` 可派发；整体仍阻断。
5. 阻断码为 `roles_not_fully_runnable / capabilities_not_fully_runnable / tools_not_fully_runnable / routes_not_fully_runnable`，七页显示完全一致。

## 专项、累计与静态验证

| 验证 | 结果 |
|---|---|
| API/Store 累计 Pytest | `40 passed / 1 unrelated baseline test deselected` |
| Web 全量 Vitest | `198 files passed / 1980 tests passed` |
| R02 targeted backend | `3 passed` |
| R02 targeted web | `4 files / 19 tests passed`（随后全量覆盖） |
| `git diff --check` | `GREEN` |
| Vite production build | `BLOCKED_BY_BASELINE` |

Vite build 的阻断来自未触碰文件中的既有类型错误：`ProductionContractsPage.tsx` 缺少 `productionContextRef`，以及 `W1InteractionHonesty.test.tsx` 的 `listObjectTypes` 假对象不满足当前类型。后端排除的测试固定断言旧插件 revision `agnes-text@2`，而当前批准 revision 已漂移；均不由 R02 引入。

## 浏览器验收

使用当前 `w1-aip` 前端 `5174` 与 API `8080`，在 `org-org/dev-project` 对以下页面逐页复验：

- `/aip/studio`
- `/aip/tools`
- `/aip/maturity`
- `/aip/evals`
- `/aip/agent-registry`
- `/aip/capabilities`
- `/aip/model-runtime`

七页均显示相同快照短哈希 `d9134922a44d…`、相同五类四态计数和相同四个 blocker；均无持续加载、无读取失败。完整快照哈希为 `d9134922a44d2354dd5bd87113f07b7cf198d430bbd446d1b9f80b2487e6548a`。

为了载入最终后端代码，本波重新启动了本地 API。启动过程按现有系统配置加载 12 条真实 cron 并预建已有 SSH tunnel；这是既有服务启动行为，不是 `operational-projection` 读取接口产生的数据写入或外部 Provider 调用。浏览器验收和新接口本身保持只读。

## 文件哈希

最终 `post-hash` 记录在同目录 `receipt.json`。预冻结表位于 `130-AIP接管后剩余波次权威对账与开发明细.md` §23.3。

## 回滚

回滚时移除七页共享状态条、前端 `aipOperationalProjection` SDK 与只读 Router 入口即可；本波没有迁移、没有新增持久化表、没有修改现有领域写路径，因此无需数据回滚。
