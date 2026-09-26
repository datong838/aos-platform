# W5cav｜DailyReview 首个持久目标 Owner 验证

## 第 1/6 步：上位方案复习

- 231-5 §1/§4/§5/§7 要求 ContentReview 后按 resultReceipt 自动续跑，但 EffectReview 必须有真实观察，不能把审核通过的文案冒充经营效果；栖月汇产品 §9 同样要求来源与下一行动闭包。
- m1 起点 `d184245b`；W5cau 有 `claim_current` 原点门而没有反馈目标/自然消费者。当前唯一 Alembic head 施工前为 `a0v_098`。

## 第 2/6 步：方案与文件

- 施工前方案已在 `d58ff3d0` 提交：`w5cav-daily-review-target-owner-plan-20260926.md`。本波新增 `a0v_099_ecommerce_daily_review_target.py`、`ecommerce_growth_daily_review_target.py`、单元及隔离 PG 两个测试文件。方案后记明确：`run_one` 不是进程级自动认领；下一波必须先补 selector/生命周期。

## 第 3/6 步：RED 与最小实现

- 新测试初跑因 `aos_api.ecommerce_growth_daily_review_target` 不存在而 RED。最小实现给 ACCEPT 的第 1 段 `daily_review` 加同事务 `claim_current`→写前二次 `require_current_origin`→内部目标 put→独立 Receipt readback→原 feedback ack→checkpoint readback→commit。
- `a0v_099` 只新增内部目标表与受限函数，租户 RLS、`aos_runtime` 仅 SELECT/函数 EXECUTE，stable `target_id`/`command_id` 唯一。函数重验原 Review Receipt、当前 Dispatch/Runtime、claimed lease/checkpoint/payload；生成不可变 `DailyReviewReceipt`。目标正文只写“评审通过、效果待观察”，`effectStatus=AWAITING_OBSERVATION`，不写 EffectReview/Wiki、不发送/发布/调用 Provider。

## 第 4/6 步：专项、累计与真实隔离 PG

- 常规邻近回归：47 passed，7 既有 warnings。覆盖原反馈、ContentReview、结果反馈及内容执行邻近逻辑。
- 专用隔离 PostgreSQL：10 passed，7 既有 warnings，含完整当前 Host group 的 `claim_current`→目标函数→独立 Receipt 回读→ack、同键再读不重复 attempt、旧 epoch/禁入/lease/payload 漂移拒绝、回滚无残留、dev-org 读取 0。此处是临时测试数据库，不是生产权威。
- 第一次把 opt-in PG 与依赖标准 disposable DB 的旧测试共用 `AOS_TEST_USE_SHARED_DATABASE=1` 导致旧测试缺 `twa_org`，系测试环境混用；分开运行后两套均通过。`compileall`、`alembic heads`（唯一 `a0v_099`）、`git diff --check` 均通过。`ruff` 当前环境未安装，未冒称 lint 通过。
- 专用 `aos-w5cav-regression-pg` 容器已按名停止；测试每例的临时数据库/角色由 fixture 删除。原 18181 诊断进程未碰，两个旧 `w5c8i-test-only-*` 用户文件未碰。

## 第 5/6 步：浏览器与方案/代码一致性

- 8080 无监听；18181 仍是 PID 36529 的 HTTP-only 诊断，不具 Registry/Installation 当前授权。无可合法验收的当前安装，未运行自然反馈，也未在生产应用 `a0v_099`，故浏览器/真实业务门未过。
- 代码与方案一致于“首个内部接收端”；尚无生产命令 selector/进程注册，`run_one` 本身不可称自动续跑。`improvement_observation`、`memory_candidate`、RETURN 仍 fail closed 未接线。内部 DailyReview 是已审核内容的 Receipt，不是效果成熟、总控复盘或 Wiki 正式入库。

## 第 6/6 步：结论与下一波

- 本波内部目标 Owner 和隔离事务真链完成；真实 A1 首链未完成。下一波 W5caw 先补有界反馈 selector/默认关闭的进程生命周期、只在 ACTIVE Runtime Host 下自然认领；再接 `improvement_observation` 的真实观察来源/EffectReview，保持旧命令及未知结果不重发。
