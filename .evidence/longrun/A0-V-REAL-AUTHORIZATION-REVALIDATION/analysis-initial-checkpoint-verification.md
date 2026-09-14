# SC4-3b 首步未执行的初始检查点

基线6dbd3b15，m1父Lease内修改aip_task_store.py，新增test_analysis_initial_checkpoint_pg.py。pause_run可显式checkpoint_before_first_step=True，默认False及普通请求hash不变。真值时纳入幂等hash，仅当前running/approved且从未领取任何步骤、无Checkpoint的运行可生成；按首个适用无前置步骤及attempt=1保存原_input_hash和依赖snapshot。checkpoint kind=initial-input、status=not-started，completedStepIds/artifacts/usage为空，不伪造StepRun、TAOR或经营产物。初始检查点与暂停及控制Receipt原子写入；不新增DDL。

RED：3项因缺少参数失败。GREEN：补逻辑后9项通过；追加领取后拒绝、输入漂移拒绝、普通pause兼容，累计初始检查点/原启动门/实际编译PG为15 passed（7.19s）。相同初始暂停key唯一checkpoint；普通pause不能复用该key；外层故障使checkpoint与pause全部回滚；原resume匹配时恢复running、漂移时记录invalidated并保持paused。

AR2 ar2-7 1899/177/93全部错误为空；git diff --check通过；memoryctl GREEN AOS-000573。测试是隔离TaskStore控制流程，没有模型执行或经营步骤完成。真实事件START还未使用该选项，下一SC4-3c启动Preview及审批组合，再sealed Host。不能将初始checkpoint作为画像/诊断完成依据；后续DataNeed/自然恢复仍须完整链路验证。不push，230 L0挂起。
