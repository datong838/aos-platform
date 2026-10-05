# GT原容量入口隔离修复验证

基线215e03d7/AOS-001345，Task gt-shared-capacity-entry-20261005。仅容量输入安全修复与完整物理切换方案，不是共享物理账本、首次模型评测或b90三写验收。

实际5433一次性PG中，原维护负例池分别用错tenant、model_copy改blocked/selectedRefkind、空run/带空白run调用原reserve，五次均未拒绝而真实占额：RED5 failed/6.50s DID NOT RAISE，red.log。隔离维护池与构造resolution不是合法Model/Route配置或质量正向。

最小修复保持原池选择/锁/占用/重放/过期/事件/提交算法：reserve连接前检查原scope类型、canonical bounded runID，原_exact_resolution重新parse原DTO及READY/blockers0/selected refs，并对reserve显式scope比较tenant。共享static scope可选保持原ContentBudget调用；那些resolution来自同caller同scope原Resolver，不把static当通用租户门。DTO重新parse也不证明current heads/Health/时间新鲜度，不能作为完整运行权威。

专项5 passed/6.43s。五文件相邻首轮27 passed/2 strictxfailed/41.18s；增加missing_scope拒绝及全部六故障原连接factory调用0断言后，最终28 passed/2 strictxfailed/41.30s、7既有warnings，adjacent-final.log。原普通容量101并发最多100成功/1原上限拒绝、canary空结果回归通过。真实reservation/event完整jsonb及canary前后相同。原事务factory仅加记录并委托原connect，不用替代PG完成状态。Python compile与精确diff --check通过。

两个strictxfail仍明确说明缺正式Provider物理上界账户与跨Route池共同占用，未移除或改弱。旧物理反例保持，不能因入口修复说GT-b4b已完成。独立只读route_supervisor复审确认兼容原ContentBudget静态路径和输入边界，要求后继锁图对照原Capacity→Budget；已在plan记录。

风险/下一：共享账户的正式Source/独立Owner批准/旧活跃占用完整切换、不可按Provider revision分裂、unknown不可TTL释放、同caller双预留+一次Intent、正式Model质量Suite及受限执行/Usage/Report/Gate均待。计划已列发行/消费固定NOLOGIN与FORCE RLS，当前未创建这些权限。正常原数据不改，缺正式来源不得凑物理常数或发送。

全部测试只在隔离库，真库未访问/迁移/重启，无Host/worker/现实Provider/Secret读取/商城源/旧Run/manual/230L0/外部效果。m1精确提交、不push、不改其他分支/用户改动。完整b90接续Task保持ACTIVE；Goal自然首链/八工作台/连续观察/发布pending。
