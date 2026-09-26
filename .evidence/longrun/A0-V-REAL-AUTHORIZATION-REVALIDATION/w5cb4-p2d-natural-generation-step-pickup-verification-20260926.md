# W5CB4 P2d 第三段｜已结算内容生成步骤的有界自然拾取

- 状态：代码/查询门 GREEN；默认关闭、生产未激活、当前实例候选为 0，W5CB4 整波未完成。
- 依据：`w5cb4-content-review-taskrun-feedback-plan-20260926.md` P2d；前置来源证明 `51fe641f`、事务化 AIP StepRun Owner `bbc2ecf3`。
- RED：新增 selector/worker 测试首跑因 `ContentStepUnknown` 与 `_start_content_generation_step_worker` 尚不存在而收集失败。
- 最小改动：`ecommerce_content_step_owner.py` 加有界同租户 selector，只拾取 `settled` 预算、已记录结果、同 invocation 的内容 Artifact、running 原 Run、且没有任何 `content_generate` StepRun 的 reservation；每个候选仍由 `run_one` 在当前安装和独立结果/Receipt 门重新验证。已知单项阻断可隔离，提交/独立读回未知使 worker 失败关闭。`main.py` 单独增加 `AOS_ECOM_CONTENT_STEP_WORKER_ENABLED=false` 默认门，要求活 Runtime Host 与独立 runtime DB 身份，不借内容 Provider worker 开关启用。
- 新鲜验证：专项与内容执行/Eval/Review/公共合同邻接回归 `53 passed, 7 warnings`；只读在指定 `aos_meta_head` 实际表结构运行 selector 返回候选 `0`，未读商城源；compileall/diff check 待提交前复核。无前端改动，无浏览器验收。
- 明示缺口：当前 DB 仍在 `a0v_092`、无本链内容结果，不能证明生产自然运行；隔离测试对完整预算/当前安装作局部 fixture，尚须全链同库联动。selector 当前只处理首个无 StepRun 的生成结果；RETURN 后的新 attempt/新产物必须另行按 ReturnDecision exact 绑定接续，绝不能复用旧 Provider 结果或将本段 GREEN 扩张为退回路径完成。
