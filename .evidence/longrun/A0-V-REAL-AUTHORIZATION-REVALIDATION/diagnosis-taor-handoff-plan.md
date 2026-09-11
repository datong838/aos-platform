# D02 TAOR 阶段交接方案

2026-09-11，m1 27d66750，AOS-000573。承接 231-5/231-6 和 diagnosis-generation-composition-plan.md；单人串行、不 push、230 L0 挂起。

## 产品缺口与行为

当前 CanonicalTaorRunner 一次遍历所有剩余步骤，D02 专属工作者若直接复用，会在诊断完成后错误领取方案设计步骤。需要明确阶段边界：画像已完成时只运行诊断、保存正式 Decision 检查点，保持整条 Run 运行中，把方案设计留给正式 D03 工作者。阶段返回不冒充整任务完成，真实宿主后续须按检查点自动调度下一位数字同事。

## 修改目录

- `services/aos-api/aos_api/aip_taor_loop.py`：新增默认关闭的 stop_after_step。存在且唯一的计划步骤才能作为边界，边界后不得 claim；末步保持 complete_run。边界已完成时验证历史观察及之前步骤完整后无重放返回，不能补跑乱序历史或越过边界。
- 新 `services/aos-api/aos_api/ecommerce_analyst_diagnosis_worker.py`：绑定三阶段批准Plan完整hash、同租户Task/Run/AgentRun、D02指定实例、稳定tenant+Run+Plan+diagnosis attempt且attemptNo=1。只允许portrait已成功；think核对原画像检查点和当前来源，act重新校验谱系并调用DiagnosisGenerationService，verify按Owner回读正式诊断，observe只保存exact引用，启用慢调用续租，stop_after_step=diagnosis。
- 新 `services/aos-api/tests/test_ecommerce_analyst_diagnosis_worker.py`，新 `services/aos-api/tests/test_aip_taor_stage_boundary.py`；既有诊断receiver测试fixture可补参数化三阶段真实Plan/稳定attempt，仅合成隔离数据库。

## 失败与权限

未知调用或当前来源/谱系不匹配使用受控blocked异常保留原调用，不走通用failed自动重试。阶段完成检查点沿用当前Owner原子提交；不修改已有D03、旧默认Runner与公开入口。不创建正式业务授权、不直接补真实租户状态。

## 退出与后续

验证边界非法时零claim、阶段成功后无后继claim/不提前终态、新工作者恢复不重复阶段；D02谱系漂移/画像引用漂移/未知结果拒绝。一次性完整PG验证成功诊断→两检查点/整Run running/第三步未领取/一份原Artifact，原D03与续租/观察恢复回归。形成证据与提交。

下一波D01指标/方法/Eval正式来源及生成，再正式AgentRun创建/职责配置/三阶段宿主连续调度；真实数据恢复后经营参谋计划首链、八工作台真实场景与观察，整体未完成。
