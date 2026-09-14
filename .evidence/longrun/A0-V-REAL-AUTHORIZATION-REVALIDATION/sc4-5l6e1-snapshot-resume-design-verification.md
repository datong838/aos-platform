## SC4-5l6e1 原快照Fulfillment与续跑技术分解（2026-09-15）

基线ec43ca4c，m1单人串行，不push，230 L0挂起。新增snapshot-resume-design.md，核对14个原权威文件与ar2_008原写入函数：DataFulfillment支持真实EvidenceBundleRevision，但必须符合原requestedOutputs；旧hydration Saga仍强制其真实水合回执。新快照分支保留原Task/TaskRun/业务Run/checkpoint/CAS/原统一Receipt，不构造假mapping或hydration。

关键边界已登记：WAITING_DATA/paused只读守卫不能包住成功状态转换；原初始化/dispatch、完整投影/安装控制、Binding作为覆盖事务的外层，阶段A待数据精确核验结束后阶段B原状态Owner转换，转换后核原预期状态Receipt，不重新要求旧状态。内部session限同tenant+backend/transaction+active+exact命令，不允许返回跨事务许可。Fulfillment首次用DBclock，重放复用原fulfilledAt并current核验，不因重试now改变幂等。

技术分波已补l6e2真实原Fulfillment、e3严格命令/结果、e4当前授权会话、e5原Task/Run/Host接线、e6原初始链PG验证，之后l6f Outbox与l6g主升级/真实首链/八场景/观察。每波具体文件在新方案表登记，接口缺口先补计划再编码。当前只完成方案，不称续跑实现或测试通过。

只读主库核对：既有容器aos-a0v-recovery-pg内部用户连接aos_meta_head，READ ONLY/ROLLBACK，schema a0v_038；业务Requirement在payload。指定org-org/dev-project后原head关联查询未返回当前需求，不能据此判断别的DB或服务任务，不假设真实requestedOutputs。首次直连无密码/默认postgres不存在及SQL引用错误均未执行写入；后续复用既有容器用户完成只读核对，未索要/输出口令。尚需主联调验证实际服务连接。

方案检查：14个引用权威文件存在，git diff --check通过；设计波无新增业务代码、无主库/任务/商城/Provider变化。下一波l6e2从原Bundle/Readiness生成exact Fulfillment并验证完整12实际PG幂等/current/rollback；旧用户文档和Playwright依赖改动保留。
