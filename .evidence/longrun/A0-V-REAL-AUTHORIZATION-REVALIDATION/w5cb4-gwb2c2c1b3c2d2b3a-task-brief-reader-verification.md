# GW-b-2c2c1b3c2d2b3a v3 Task/Brief 读者验证

基线 `AOS-001126` / `m1 af6e7de7`；方案 `w5cb4-gwb2c2c1b3c2d2b3a-task-brief-reader-plan.md`。复习 231-5 §1/§9、栖月汇六同事统一 Task/Handoff 与 D-waves。

- RED：在一次性 PG 用原 ReviewAdvanceHostService 写 v3 Task/Brief 后调用生成宿主读者，原 `_task_brief` 不接受 `source_kind`，1 failed/4 deselected，退出1。
- 最小实现：新分支仅在调用方显式提供 17 项独立 `source_lineage` 时，校验同一原 Artifact 与 GrowthPlan/Handoff/Task、Task.goal/Brief.spec 来源全等、Brief schema v3。缺 expected、markings 漂移和 Artifact 身份漂移均拒。旧默认仍用 Issue v1/v2 合同；Host.revalidate 对新分支先失败关闭，尚未调用此读者。
- 隔离 PG 专项及相邻五文件 69 passed、7 warnings，退出0；`py_compile`、`git diff --check` 退出0。测试 PG 自动销毁，当前命名库仅作签名 preflight 身份读取。
- 一致性/风险复审：读者 expected 不能来自 Task/Brief 自身；当前测试来源来自同一原 Review 命令，只证明读者形状与 hash/同事务读取，不等于正式当前 Stage Owner/Receipt。接入新分支必须由原 StageDecision/Eval/permission/GrowthPlan Owner 独立产生 expected；在此前继续禁入预算/Provider/Host。不宣称内容产物或首链。
- `m1@a6460d87` 后重载 API/Web（PID37064/37066，健康与技能路径 HTTP200，18181无监听），浏览器异步加载完成后技能页37仅评测、三 blocker、发布按钮 disabled、工作台无入口。首次页面读取处于加载中，未用该瞬态作结论；第二次完整 AX 状态核到上述结果。页面保留给用户。PG 沿用当日已重启权威卷。

下一切片 d2b3b：实现原 Stage Owner + Handoff/Review Receipt 独立 exact 读者，并把上述 v3 Task/Brief 读者接入 revalidate，仍需可读 Artifact 与人工评审消费者齐备才打开执行门。正式 OIDC/八配置/Growth1.13/assignment/binding 另门。
