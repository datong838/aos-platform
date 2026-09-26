# W5CB4 P2g｜同一原对象的只读内容评审候选

- 基线 `m1@ee473b6c`，先补第六增量文件级方案；仅延伸 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py`。沿同一正式 `a0v_105` 一次性库、原 TaskRun/Reservation/command/runtime Receipt、settled Artifact、成功 StepRun/checkpoint 与当前合同的正式主体通过报告；没有插入伪报告或伪 Issue。
- `ContentReviewPendingReader.read_one` 除显式业务 context Source 接缝外不替换报告、合同、Plan、StepRun、dispatch 或其他正式查询。首次与重复只读返回相同 exact `(Reservation,Run,Task,Artifact/hash,StepRun,Report/revision/hash)`；读前后唯一 EvalRun/报告/生成 StepRun 保持 1，ReviewIssue 保持 0。
- 负向：对 `dev-org/dev-project` scope 查原 reservation 得 `content reservation unavailable`；在隔离库把当前 dispatch fence 置真后读取器以 `ContentReviewPendingBlocked` 拒绝，恢复 fence 后仍是原候选。测试对 fence 的写入仅限会自动删除的测试库；不代表当前实例安装可执行。更多旧 attempt、合同撤销、重复/失败报告及已有 Issue 的同库负例留后续波。
- 专项 `1 passed, 6 deselected, 7 warnings`；内容、通用 EvalRunner 与邻近 PG 累计 `294 passed, 35 skipped, 7 warnings`，`git diff --check` 通过。纯后端只读候选证据，浏览器验收不适用；未开放 GET、未创建 ReviewIssue、无 Provider 外呼/商城源读取/旧 12 Run 重放或 230 L0 推进。
- 下一波：继续同库候选漂移负例与正式 Issue 创建/人工 resolve 权威的文件级方案；完整 Host 锁、自然 Provider/真实事实及生产安装仍需独立闭环，不能因测试候选成立就启生产。
