# 原始待处理需求上下文验证

### SC4-5j3a 原始待处理需求上下文验证

AnalysisPendingDataContext复用原AnalysisContinuationContext事务，参数仅原receipt_ref与同步consumer；原Run验证WAITING_DATA/RUNNING及pending ref，原DataRequirement精确/当前版本一致、未过期、无blocker，原Case/Compilation/TaskRun/Checkpoint、Profile/facts/purpose/cutoff逐一核对。原窗口/阈值不修改，消费前后重读并校验载荷hash；不产生Readiness/Fulfillment或执行经营步骤。

Red因模块未实现而失败。首轮7 passed/2失败，失败为测试取消操作actor与createdBy不符，修正夹具沿原created_by执行，生产规则不变。新增9项+原需求创建18项合计27 passed/37.88秒；再补无pending和已取消Run两项后新模块11 passed/15.67秒（7 warnings）。实际PG原请求/暂停/取消Store与原分析continuation运行；源与能力沿用明确fixture double，漂移场景部分为reader double。不能称真实完整首链。没有源调用、主库迁移/安装或模型执行。

AR2初次发现新Host模块未分类；复核其仅协调Host权威且使用原growth Profile目录，清册新增Host分类一行及初始hash，旧preHash与验证器不改。复验1931扫描/188分类/93迁移，五类错误为空；强一致投影CURRENT、memory-validate GREEN，Codex eventual PENDING_ASYNC仍不阻断。

下一波SC4-5j3b：组合原pending上下文、原completed snapshot上下文与当前安装导出的SnapshotBusinessCohortPolicy，实际需求窗口/purpose绑定到selector，并保留缺时间/缺父unknown。只给出受控样本输入，不冒充逐事实字段质量或合格Fulfillment；后续正式字段计量、原Outbox消费者、主环境安装切换、真实首链/八场景和持续观察仍未完成。
