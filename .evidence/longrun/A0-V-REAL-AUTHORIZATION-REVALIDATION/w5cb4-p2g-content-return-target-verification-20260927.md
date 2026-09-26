# W5CB4 P2g24：人工 RETURN 内部返工目标接收验证

日期：2026-09-27。方案先行 `m1@5cca156a`。范围只含 `ecommerce_growth_content_return_target.py`、其专项测试和原 `test_ecommerce_content_review_pending_pg.py` 同库夹具；没有迁移、当前库写入、API/worker 启用、商城源读取、Provider 调用或旧 Run 重放。

## RED、实现与新鲜验证

- RED：新增专项最初因 `aos_api.ecommerce_growth_content_return_target` 不存在而在收集期失败；随后才新增实现。原同库 RETURN 路径先被正式 `RETURN_PLAN_DAG_MISSING` 拒绝，按 231-5 的依赖要求补夹具的 `content_generate→content_review` 正式 DAG，没有绕过 AIP 返回门。篡改 ReturnDecision 的探针被数据库 `AIP4_APPEND_ONLY` 拒绝，测试改为保存这个实际拒绝事实。
- 正向：一次性完整 `a0v_106` 克隆、同一原 Task/Run/Artifact/Eval/Issue 与正式人类 `return_review_issue`，生成同 Run 的 `content_generate` 第 2 次 queued StepRun；ContentReview Host 持久化唯一 RETURN Receipt 和单段 feedback。非超级 `aos_runtime` 在九操作 Host 锁下 `claim_current→require_current_origin→只读已有 ReturnDecision/queued StepRun→acknowledge`，反馈 checkpoint=1、attempt=1、target Receipt 独立连接回读。重复调用只读回原 Receipt；未创建第三次生成尝试。
- 负向：九操作锁缺失时不可接收；`dev-org/dev-project` 仅零 canary，读不到正租户目标；content-review dispatch fence 后不可接收；数据库拒绝篡改不可变 ReturnDecision。单元覆盖错序号/种类/attempt/target、错 decision hash/step/artifact/Issue/Run 与提交、独立读回、回读漂移未知边界，未知抛 `ContentReturnUnknown`，无第二次 claim。
- 新鲜输出：新目标专项 `13 passed`；整份内容评审同库与目标专项 `21 passed`；反馈端口、当前评审 Host、AIP 返回与同库链累计 `42 passed, 3 skipped`；终态 Owner/原反馈消费者/目标邻近累计 `54 passed, 30 skipped`。`compileall` 通过，`git diff --check` 通过，单迁移头 `a0v_106`。

## 方案/代码一致性与边界

- target Receipt 不是纯内存 hash：它由同租户不可变 ReturnDecision、原评审 Host Receipt、AIP queued StepRun 的 exact 标识与返工 feedback target 唯一反查计算，并由 feedback checkpoint 持久保存。历史 ack 可回读；首次接收必须 StepRun 仍 queued、原 Run running/Task executing、当前 Host revalidate/verify_receipt 全通过。原 Artifact 不修改，预算/审批不继承。
- 本波只有可显式调用的 `ContentReturnFeedbackWorker.run_one`，**没有自然 selector/serve/startup flag**；当前实例 8080/18181 仍无监听，恢复 PG 仍受 `STOP_MIGRATION / STOP_CURRENT_API_AND_WORKERS` 限制。浏览器本波不适用。隔离夹具中的人类决定不等于真实用户操作、签名安装或自然经营闭环。
- 下一波优先补独立默认关闭的 RETURN selector/worker、Host 停止时 fail-closed；之后才设计返工生成的新版本/新预算/新批准与浏览器恢复入口。不得把已 ack 的退回目标当成内容已重新生成或任务完成。
