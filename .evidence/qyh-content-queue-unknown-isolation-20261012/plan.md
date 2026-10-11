# QYH 内容队列未知结果隔离

Rules：231-5第6/7节、原Host/预算/Receipt门、仅m1单写，未知不重发、局部失败继续安全独立项。用户已授权231机制/恢复施工和持续Loop，原流程修复不新增业务权限。基线2b080ab7b/AOS-001902。

候选一：现有Content Host队列的unknown异常隔离，独立可修复且优先；候选二：正式OIDC/publisher配置接入，需已有真实配置来源；候选三：Media source BundleManifest/四Rule producer接线，需单独精确合同。完整八工作台/自然首链不缩小。

调查纠正：上一波统计是通用AIP content_draft；电商实际使用ContentGenerateHostService→原budget hold→execution command→CurrentContentPreparation→worker提交→result consumer持久Artifact/Usage路径，已经实现不少功能。不能依据generic路径缺口把该路径丢弃或重建账本。其当前是否有记录另核实，不能从generic统计外推。

问题：worker已提交后Provider异常、未知落盘失败、结果落盘失败均抛ContentExecutionFailure。run_pending仅catch ContentExecutionConflict，因此单项已知需对账异常终止整轮，不处理后续独立项。

文件：services/aos-api/aos_api/ecommerce_content_execution_composition.py导入原ContentExecutionFailure并在run_pending精确catch，返回该reservationId/status=RECONCILE_REQUIRED，然后继续；新tests/aip/test_content_queue_unknown_isolation.py；本Task证据和本方案文档。不改worker提交/unknown/预算锁、不修改dirty原预算writer。

验证：RED证明首项已知unknown阻断第二独立项；GREEN覆盖未知及持久化失败、其他任务可处理、其他未归类异常仍显式失败、run_once会继续结果消费但不重发未知、下一轮仅处理journal原pending结果。相邻原composition与真实独立PG worker/result消费测试，使用18431标准临时DB，PGskip不能算通过。精确源hash/diff/秘密扫描、方案复审和Delivery/CAS/sync。无页面修改；不启worker/Provider、不改真库、不授自然首链。失败结果不能标COMPLETED。

相邻RED诊断：旧prepare测试夹具row.request_hash=item.requestHash（业务命令内部摘要），原读者要求完整command canonical prefixed hash。生产校验未由本波改变，补独立精确Task仅修夹具该一行，不放宽读者。

实际测试设施核对：29passed/0skip，18431 clone postgres唯一ar2_budget_*schema及autouse临时DB均清理。真实远程调用未执行；本修复只候选m1，运行API不切换。当前电商内容command/result/artifact亦0。原用户预算writer hash保持。
