# W5caw｜首段评审反馈自然消费者验证

## 第 1/6 步：方案复习

- 231-5 §3–5 的真实要求是人工 Review 后由持久命令自然续跑，且旧代次/未知结果不得重发；W5cav 只有可调用的 `run_one`，不是自然消费者。栖月汇产品的效果复盘仍需真实观察，不能用首段待观察文案冒充。

## 第 2/6 步：文件级方案

- 施工前方案 `w5caw-natural-feedback-consumer-plan-20260926.md`，m1 `f224bb69`。变更限定 `ecommerce_growth_feedback_consumer.py`、`main.py`、自然消费者测试和隔离 PG 测试；没有修改旧 Run、Provider、商城源或其它分支。

## 第 3/6 步：RED 与最小实现

- 新测试先因消费者模块不存在而 RED。新增只读取 `pending/attempt=0/checkpoint=0` 的 ACCEPT 首段 selector，按租户、唯一 Review Origin、当前 content_review Dispatch/Runtime、目标不存在及上界 32 限定。已 claim、UNKNOWN、旧 epoch、禁入不出队；出队后仍由 W5cav `run_one` 全组锁和二次 fence 守住竞态。
- `main.py` 新增 `AOS_ECOM_FEEDBACK_WORKER_ENABLED` 默认关闭的启动入口，只有同进程 ACTIVE Runtime Host 和 host-only runtime DB 身份有效时启动；复用 Host stop 事件，没有第二 Host。错误 fail closed；未打开该开关的现有路径不变。

## 第 4/6 步：专项、累计、PG

- 普通邻近回归 56 passed，7 既有 warnings；`compileall`、唯一 Alembic head `a0v_099`、`git diff --check` 通过。
- 专用隔离 PostgreSQL 15 passed，7 既有 warnings：selector→原 `run_one`→target/ack，二次扫描空；claimed/UNKNOWN/旧 epoch/禁入全部 0。专用 `aos-w5caw-regression-pg` 容器已停止，测试临时库及角色由 fixture 删除。
- 本波没有真实生产迁移、没有调用 Provider、没有读商城源，也没有人工重发旧命令。

## 第 5/6 步：浏览器和一致性

- 8080 无监听，18181 仍是旧 HTTP-only 诊断 PID 36529；没有当前已授权安装，因此无法做真实浏览器/自然周期验收，也没有启用反馈开关。隔离 PG 的自然扫描只证明机制，不证明目标租户现场已经自动回流。
- 方案/代码一致：当前只自动消费 ACCEPT 第 1 段；后三段与 RETURN 未接线，效果观察/EffectReview/Wiki 候选仍未实现。对具体实例无可信安装时只挡活体，不再转头补旧 12 Run 快照。

## 第 6/6 步：结论与下一波

- 首段自然消费者代码与隔离 PG 闭环完成；真实 A1 业务首链未完成。W5cax 下一步：`improvement_observation` 的真实观察来源与 EffectReview Owner，严守无样本不得宣称成熟、无当前安装不执行；之后才是 Wiki 候选、RETURN 与真实安装/两自然周期验收。
