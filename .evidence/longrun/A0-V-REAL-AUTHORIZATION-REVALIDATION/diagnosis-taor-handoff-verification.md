# D02 TAOR 工作阶段交接验证

2026-09-11；m1 基线27d66750；A0V-D02-TAOR-HANDOFF-20260911；AOS-000573。方案 diagnosis-taor-handoff-plan.md，五文件pre/post SHA256见diagnosis-taor-handoff-files.json。

## 结果

新增DiagnosisTaorWorker校验当前运行三阶段Plan、批准hash、同Task/Run/AgentRun、D02指定实例与固定attempt身份。前序画像exact回读后调用受控生成服务；正式诊断按Owner和原调用Artifact回验，只存exact检查点。未知结果阻断，不自动重发。启用既有慢调用续租。

CanonicalTaorRunner新增默认None的stop_after_step：非法/重复边界零claim，诊断完成后整Run保持running且不claim方案设计；最后一步仍走原complete_run。历史边界完整时无重放返回，缺前序拒绝，旧默认调用不变。

专项68 passed。扩大相关范围后：**286 passed，7既有warning，18.05 s，退出码0**。执行环境AOS_DOTENV_DISABLED=1、AOS_TEST_USE_SHARED_DATABASE=1、AOS_GROWTH_DRAFT_FULL_GRAPH_TEST=1、AOS_GROWTH_DRAFT_OWNED_CLONE_TEST=1。范围为diagnosis_worker、taor_stage_boundary、taor_lease_adapter、taor_observation_recovery、diagnosis_service、diagnosis_receiver、diagnosis_generation、analysis_proposal、analysis_sources、growth_plan_receiver、growth_plan_full_graph、authority_store、growth_plan_worker、growth_plan_generation对应14个测试文件。

新增4组完整一次性PostgreSQL验证：三阶段分次交接/同边界新实例零重放；D02成功恢复原回答后两检查点/一原Artifact/整Run running/方案设计无step记录；错误画像与未知生成保持一检查点、无诊断观察。新三阶段Task/Plan/Run由真实Owner建立批准，AgentRun/原成功调用/业务事实仍为合成FK夹具。原D03工作者、续租暂停取消fence和观察恢复回归通过。git diff --check通过。退出后既有JDBC关闭日志流提示不影响退出码。

## 未验收与下一步

没有实际Provider、主库业务写入、API重载或真实宿主自动调用。当前阶段工作者需已建AgentRun和明确调用，不能把内部组合测试当成无人手工接线的真实业务验收。D01方法/指标/Eval权威、D01生成/阶段工作者、正式实例和运行创建、三阶段宿主、真实源恢复、经营计划首链、八工作台场景及持续观察仍待完成。

下一波补D01正式来源。保持用户经营初心，不push，230 L0挂起，整体未完成，自动进入下一波。
