# W5cax｜内容 TaskRun 正式终态反馈门禁验证

## 第 1/6 步：上位方案与偏差

- 已复习 231-5 §4 与 231-9 §3.7–8：首段反馈必须在内容 TaskRun 正式终态之后；W5caw 的 selector 和 W5cav 的目标写入先前缺这道门。不能把 Review 已接受或内容 Artifact 已记录等同于任务完成。

## 第 2/6 步：文件级施工

- 施工前计划 `w5cax-content-terminal-feedback-gate-plan-20260926.md` 已在 m1 `6907febd` 落盘；复审后修正为不改已提交 `a0v_099`，只新增 `a0v_100`，本提交连同实现收口。
- 修改 `ecommerce_growth_feedback_consumer.py` 的只读 selector、`ecommerce_growth_daily_review_target.py` 的受限函数入口，新增迁移 `a0v_100_ecommerce_daily_review_terminal_gate.py`；测试只改对应消费者单测和目标隔离 PG 测试。没有碰旧 12 Run、商城源、Provider 或其它分支。

## 第 3/6 步：RED 与最小实现

- RED：未终态的 Artifact→TaskRun→Task 仍能出队/写每日复盘目标，两项测试先失败。
- GREEN：selector 要求 exact Artifact 类型/哈希/修订、同租户 Run `succeeded`、同任务 Task `completed`；新 SECURITY DEFINER 入口同事务调用旧写函数，再独立复核终态，失败抛错回滚。撤销运行角色对 `a0v_099` 旧写入口的执行权，保留历史迁移原样；`a0v_100` 不支持不安全 downgrade。

## 第 4/6 步：专项与累计回归

- 普通邻近测试 70 passed；隔离 PostgreSQL 目标与反馈端口 33 passed。缺 Run、running/failed、未完成 Task、Artifact 类型/哈希/修订/Run、Run Task 漂移均被挡；旧函数的运行角色 EXECUTE 已撤销。7 个既有 warning，非本波引入。
- `compileall`、`git diff --check` 通过；Alembic 唯一 head `a0v_100`；`a0v_099` diff 为空。专用 `aos-w5cax-regression-pg` 已停止。
- 扩大尝试 `test_ecommerce_content_generate_handoff_lineage_pg.py`，单独复跑也因专用最小 PG 无完整 `aip_task` schema 失败；这是不同 fixture/数据库前置条件，不算绿，也不是本波门禁回归失败。后续在完整隔离 schema 补测。

## 第 5/6 步：浏览器与一致性复审

- 8080 无监听；18181 仍是原 HTTP-only 诊断 PID 36529。没有可信当前安装/生产迁移授权，故无真实浏览器自然周期验收、没有开启反馈 worker。
- 方案与代码一致：该波只在首段目标写入前增加正式终态门；不伪造 TaskRun、不补历史结果、不宣称 EffectReview/Wiki 或业务闭环完成。旧函数授权已撤销，但迁移尚未在真实库执行，现场不能据此宣称生效。

## 第 6/6 步：下一波

- W5cax 代码与隔离验证完成；真实首链仍未完成。W5cay 先找出内容 TaskRun 的真实创建/完成 Owner，并在自然生产内容与评审后绑定正式终态；之后才推进 `improvement_observation` 的真实来源和 EffectReview。未知结果继续只读对账，不重发；230 L0 仍挂起，dev-org 只作零 canary。
