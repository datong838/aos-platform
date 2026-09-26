# W5cax｜内容 TaskRun 正式终态作为反馈准入门（施工前）

## 上位重读与顺序修正

- 231-5 §4 将 `feedback_pending` 明确放在「TaskRun 终态→EffectReview→总控及 WikiCandidate」之后；231-9 §3.7–8 将评审续跑与真实复盘分开，首先衡量资料/解释/任务完成，不能编造成交。
- W5caw `aab96a98` 的自然 selector 仅核 Review 原点/安装和未触达状态，未要求内容 TaskRun 正式终态；W5cav 的目标函数也未要求。当前 Review Handoff 创建 Task/Brief，ContentResultConsumer 记录 Artifact/Usage/Budget，但未发现自动 `complete_run`。直接启用反馈开关会早于上位规定，必须先 fail closed。

## 文件级施工

1. 修改 `services/aos-api/aos_api/ecommerce_growth_feedback_consumer.py`：只读 selector 加 Artifact→同租户 TaskRun→Task 的 exact join，要求 `aip_artifact` 内容 hash/revision/type 与 feedback command 一致、artifact.run_id 对应 `aip_task_run` 且 status=`succeeded`、Task status=`completed` 且 task_id 一致。缺失/运行中/失败/跨租户不出队。
2. 修改 `services/aos-api/alembic/versions/a0v_099_ecommerce_daily_review_target.py`：同一目标函数在写入前独立复核 Artifact/Run/Task 终态，避免直接调用 `run_one` 绕过 selector；必须在任何目标写入前完成。
3. 修改隔离 PG fixture `test_ecommerce_growth_daily_review_target_pg.py` 和单元 `test_ecommerce_growth_feedback_consumer.py`：先 RED 证明未终态现在误出队/误写，GREEN 后测 succeeded/complete、running/failed、artifact hash/type/Run/Task 漂移、dev-org、回滚与旧门的累计回归。没有真实运行库授权时不开反馈 worker、不做生产迁移。
4. 本波只加终态门，不伪造 TaskRun 终态；从代码追踪给下一波 W5cay 的自然 TaskRun 创建/完成 Owner 文件级入口。EffectReview/Wiki 候选随后再接，不将安全阻断当业务完成。

## 退出

- 验证、代码/方案复审、m1 提交、D-waves/AOS/Prime 更新后自动进入 W5cay。若真实 TaskRun 当前不存在，保持 pending，不补旧 12 Run、不手工 run_definition、不人工改库救场。
