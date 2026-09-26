# W5caq｜内容持久 PENDING 交接核验

## 上位与施工边界

上位：231 A1、231-5、231-6 AR2-6/N7（本波异步非终态补充）、栖月汇双侧增长产品方案；先行文件级方案 `w5caq-content-durable-pending-handoff-plan-20260926.md`。基线 m1 `5888ceff`。本波仅把已验证 v2 内容请求在原 HostTransaction 中经原预算 Owner 创建 HELD Reservation，并把 exact 命令存进原 `ContentExecutionJournal`；返回严格 `PENDING` **非终态**。无 Provider/Usage/Artifact/外部发布、无 worker 启动，也未部署新包。旧 v1 仍 `FAILED_NO_EFFECT`，原三种终态定义未变。

## RED/GREEN 与新鲜验证

1. 包侧先 RED：`ContentCapabilityReceipt` 拒绝 PENDING；实现后只接受 Budget=`HELD`、`WAIT_FOR_RESULT`、零 Provider/Usage/Artifact/外部效果的 PENDING，污染字段拒绝。未改已签名候选包。
2. 原 `HostTransaction` 新增窄的 enqueue/read 方法，把同一底层连接交给已存在 Journal；不会暴露 commit 或任意 SQL。原预算 Owner 内抽出初始 HELD/Invocation exact Ref 计算，reserve 与后续 PENDING 重放共同复用，避免 Host 复制哈希算法。v2 Host reserve→enqueue→PENDING；Journal/预算不一致失败即 Host 事务回滚。历史 PENDING 通过原预算当前 Owner、原始 Ref 算法与 Journal exact 命令读回，即使预算已进入 SUBMITTED 也不重发、不改写为终态。
3. 新增隔离 PG 测试：同事务预算/命令提交可回读；显式回滚后两者均不存在；v2 Host PENDING 后预算进入 SUBMITTED，原回执仍 exact 回读，同命令走持久回放且不再 reserve。测试只在临时空 PostgreSQL 容器的随机 schema，未连接真实业务库；该容器已停止并自动移除。测试夹具固定 9 月 8 日审批已过期，改默认当前 UTC，产品审批规则未更改。
4. 专项及相邻累计 13 文件 **212 passed、7 既有 warnings**；`compileall` 与 `git diff --check` 通过。无 UI 变化，浏览器 N/A。未进行真实 Provider/自然场景验收，不能把 PENDING 或隔离测试写成可读内容产物。

## 方案一致性、风险与下一波

PENDING 是持久接收凭据，不是结果状态；只有后续正式消费并独立读回 `COMPLETED` + 可读 Artifact，或明确 `FAILED_NO_EFFECT`/`UNKNOWN`，业务才可进入相应下一步。现有 `ContentExecutionWorker`、`ContentResultConsumer`、`ExactProviderInvoker` 仍是未接正式 selector/启动生命周期的孤立组件；当前已签名候选包也未含 PENDING 合同。后续必须出新包版本并做安装代次迁移，不能原地改签名包。测试仅证明持久接收与回放，未证明当前真实安装/审批/出境/模型/事实、自动 worker、唯一外呼、计费、产物和人工续跑。

W5car 下一步：复习原 worker/consumer/invoker 与 231-5 安全门，写正式 selector/prepare/启动、结果回流和只读状态查询的文件级方案；先测试不可调用/UNKNOWN/崩溃重启，才允许在当前授权下做有界真实调用。旧 12 Run 后置、不重播；不读商城源，230 L0 挂起，dev-org 零 canary，m1 单写不 push。
