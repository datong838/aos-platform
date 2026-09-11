# Analyst stage review Owner 双事务绑定验证

日期：2026-09-12

基线：`646c79c3`

结论：StageDecision 真实 head/Receipt 已进入双事务 current snapshot，四种已安装包校验齐全后可由既有唯一 Owner 原子发布；真实 Task/Plan/Run、职责、runtime 和 Eval 复合 authority reader 尚未实现，因此产品入口继续未接线。

## 实现与方案一致性

- 旧同步命令的内联身份判断提取为 `require_stage_review_command_identity`，旧 service 原位复用，actor/scope/key/version/stable id/content hash 条件未改变。
- `StageReviewDecisionOwnerBinding` 只接受构造时固定 `TenantScope` 和 exact 五字段 JSON 命令；prepare/current 两事务均先取得相同两个排序 advisory lock。
- 每次读取真实 StageDecision head 与同 key authority Receipt。新发布路径要求 Receipt 为空；已有 Receipt 在 authority reader 前拒绝并保留给 Owner replay fast path，避免重跑历史来源或四门 IPC。
- trusted `read_authority` 必须提供非空 authority snapshot 和 command/slot/runtime/eval 四种唯一 exchanges；exchange canonical hash 与 head/tenant 一同进入 prepared snapshot。
- publisher 再次复核四个 results 与 prepared expected exact 相等，只调用现有 `AnalystStageDecisionStore.put`，没有新增写表或第二写者。

## 自动验证

- 真实隔离 PostgreSQL 定向测试：`44 passed`，覆盖新发布、Store exact 回读、已有 Receipt 快速拒绝、IPC 期间竞争 head 漂移零发布、四门缺失/重复零写，以及旧同步 accept/replay/revoke/回滚。
- 阶段评审全回归：`131 passed`。
- command 与 owner binding `compileall` 通过；`git diff --check` 通过。
- AR2-7 closure 扫描 1777、分类 140、迁移 93；hash、正反依赖、跨层 import 与动态引用错误数组全部为空。
- 测试退出后的 JDBC cache logging 对已关闭 pytest 捕获流报错是既有进程清理提示，测试退出码为 0，缓存计数均为 0；本切片未修改该路径。
- 既有 7 条 warning 为 Pydantic 字段遮蔽及 Starlette/httpx 弃用提示，本切片未新增 warning。

## 当前 SHA256

- command：`b2477ad290264f084f8e36b1d7f121563c499d99a2f21b460553c7d0227452b6`
- owner binding：`e573beaeea089b9ce6360e7792fed8fa625ae5c28b55b6a13ddaffe1d1c34b9b`
- command tests：`772e8919e42c467d87fc71bc0683504f2173426ff2de010f6e21276b3728b8ff`
- owner binding tests：`5787623c9d8d3bd806b6701785f9ea48d322e52e1be55f1b554a290d8f7ff864`
- plan：`e47cd065be1507bb8366e2fc08b6f0d2b2428e99b4985e73069ac0bfbca6df66`

## 风险与下一门

本波真实证明 Owner 事务与写入，并未证明测试 `read_authority` 中的简化 snapshot 是业务授权。绑定器没有产品入口，不能直接用于栖月汇首链。下一波实现真实复合 authority reader，复用现有各 Owner/Reader 一次读取 Task/Plan/Run、StepRun、Checkpoint/Observation、Responsibility/Resolution、生成来源、Eval contract/report/gate，并生成四种包消息；随后才能增加 Owner replay fast path 和产品级异步 service。
