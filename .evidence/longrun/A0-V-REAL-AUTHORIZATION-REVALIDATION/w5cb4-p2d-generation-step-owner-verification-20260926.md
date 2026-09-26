# W5CB4 P2d 第二段｜已结算内容的正式生成 StepRun Owner

- 状态：局部代码门 GREEN；未接自然 pickup、未启生产、未发生 Provider 再调用；W5CB4 整波仍未完成。
- 计划与前置：`w5cb4-content-review-taskrun-feedback-plan-20260926.md` P2d；只读来源证明 `51fe641f`。本段按原结果、预算/Usage/Provider Receipt 的独立 `COMPLETED` 证明推进原 AIP TaskRun。
- RED：`test_ecommerce_content_generation_step_owner.py` 首跑因尚无 `ContentGenerationStepOwner` 而收集失败。
- 最小实现：`ecommerce_content_step_owner.py` 增加默认未接线的 Owner。单个 serializable 事务重新核来源、原 PENDING Runtime Receipt 和当前安装 dispatch；原 Run 无任何生成 StepRun 时，通过公共 `AipTaskStore` 一次 claim、写 think/act/verify/observe 证据、complete_step。四相只引用已经提交的 Provider/Usage/Artifact，不发送新请求。已有非终态/unknown StepRun 拒绝认领；已 succeeded 仅走独立 checkpoint 与 observe Artifact 回读。
- 验证：隔离真实 AIP 数据库创建批准的双步 Plan/Run，Owner 写出一个 succeeded `content_generate` StepRun 与 checkpoint，重复调用不产生第二 attempt；当前安装修订漂移、缺独立回读、existing unknown attempt 均拒绝。累计相邻内容执行/Eval/Review/生产合同回归 `44 passed, 7 warnings`；compileall 与 diff check 通过。本段无 UI，不适用浏览器验收。
- 复审风险：完整结果/Runtime dispatch 在该隔离 AIP 测试中以受控 fixture 注入，尚未证明自然结果队列自动拾取、全库当前安装/预算联动或真实生产迁移。Owner 无 serve/自动调用；下段需做有界 selector 与完整隔离数据库同库验证，保证未知提交先读回、不再发 Provider，再谈内容 Eval 激活与人工待办。
