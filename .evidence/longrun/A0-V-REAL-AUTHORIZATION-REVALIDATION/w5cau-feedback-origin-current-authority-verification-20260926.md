# W5cau｜反馈原点评审当前权限门验证

## 第 1/6 步：上位与现场

- 按 231-5 §1/§4/§5/§7、栖月汇产品 §9 复核：反馈必须源自同一有效安装代次的真实 Review Receipt；效果观察不能伪造业务增长。
- m1 起点 `35be1006`，W5cat 为未构建未签名 1.11.0 候选，不是当前安装。现有 `ContentReviewHostService` 仅 enqueue 持久反馈命令；四个目标尚无正式执行者。

## 第 2/6 步：文件级方案

- 已先提交 `69cee6a9` 计划，随后 `629d3c9b` 明确低层 AR2-7C `claim` 与生产入口 `claim_current` 的职责差异。计划文件：`w5cau-feedback-origin-current-authority-plan-20260926.md`。

## 第 3/6 步：最小实现

- `services/aos-api/aos_api/ecommerce_growth_feedback_port.py` 新增 `require_current_origin` / `claim_current`：持久 feedback command → 唯一 Review runtime Receipt → Review/Artifact/Task/Brief/decision 精确核对 → 宿主全组 Dispatch/Runtime 锁定与当前代次复核 → 原子事务内才认领。失败不触达底层 claim、不增加 attempt。正式 Worker 只能用该入口，并须在目标写前再校验 fence。
- `services/aos-api/tests/extension_runtime/test_ecommerce_growth_feedback_current_origin.py` 覆盖当前原点、缺失/多义、内容漂移、旧/禁入 Runtime、Runtime revision 漂移的 fail-closed 行为。
- 无迁移、无 Provider 调用、无商城源读取、无目标写入。旧两个用户文件 `w5c8i-test-only-*` 未动。

## 第 4/6 步：专项与累计回归

- 专项 `test_ecommerce_growth_feedback_current_origin.py` + `test_ecommerce_growth_feedback_port.py`：12 passed。
- 邻近反馈/内容执行回归：42 passed、3 skipped（PG opt-in 未开）、7 既有依赖警告。命令使用 `PYTHONPATH=.:../../bundles/solutions/ecommerce-growth/backend:../../packages/aos-extension-sdk/python uv run pytest -q`，测试文件为 current-origin/feedback-port/feedback-port-pg/content-review-authority-feedback/result-feedback/content-execution-composition/content-execution-json/content-execution-startup。
- 首次两次收集失败分别因为未提供 growth backend 和 extension SDK 的测试路径；补全本地路径后通过，非代码失败。`compileall` 与 `git diff --check` 通过。

## 第 5/6 步：浏览器与一致性复审

- 8080 无监听；18181 仍是现存 HTTP-only 诊断进程 PID 36529，未重启或用于本波验收。无可信当前安装/真实反馈命令，本波不得称业务续跑或浏览器验收通过。
- 计划/代码一致：只实现认领前原点门；不实现四个目标、EffectReview、Wiki Candidate 或反馈自动 Worker。测试的宿主锁为注入替身，不替代真实 PG/安装证明。低层 `claim` 保留给协议测试，因此下一波 Worker 必须明确强制使用 `claim_current`；目标写前 fence 是仍待实施的必要边界。

## 第 6/6 步：结论与下一波

- 本波代码级权限门完成，真实链路仍部分完成。下一波 W5cav：从 `daily_review` 开始，设计并实现一个持久、同事务、幂等的真实目标 Owner/Receipt；以 `claim_current` 认领、写前二次 fence、Receipt readback/ack 为唯一生产通路。效果与 Wiki 候选各自分波，不能用文案冒充业务结果。
