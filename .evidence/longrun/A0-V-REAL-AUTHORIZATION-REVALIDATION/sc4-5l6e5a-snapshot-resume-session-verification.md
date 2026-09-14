## SC4-5l6e5a 快照内部恢复会话（2026-09-15）

基线27f93c5c，m1/AOS-000573。先补snapshot-resume-design.md再新增ecommerce_analysis_snapshot_resume.py、tests/test_analysis_snapshot_resume_session.py，仅在aip_task_store.py构造器显式增加exact新会话类型，旧_AnalysisDataResumeSession保留。新会话限定原Context/active stage、同backend/txid/scope、深复制严格命令hash、专属控制键与固定Host actor/reason、exact只读Profile、原Task/TaskRun所属关系/Plan/paused/精确整数版本；同步回调结束或异常均失活，重入/延迟执行拒绝。未修改普通注册表，普通_strict_analysis_command仍拒绝快照模式，尚无统一Host恢复入口。

Red新增模块缺失（/tmp/sc4-e5a-red.log）；27项新纯会话边界测试通过5.37s（/tmp/sc4-e5a-green.log），连接、stage和其他数据权威明确是named fixture，不能作为实际PG续跑证明。原test_analysis_data_resume_pg.py四项实际原Task/Run状态Owner回归通过12.62s（/tmp/sc4-e5a-old-pg.log）；其成功组合仍标明旧数据就绪fixture，缺真实Fulfillment时原阻断仍有效。两组均7项既有warnings；无新运行SQL、主库升级、商城读取或Provider调用。

另登记非重叠分类Lease追加Host原路径及初始hash 96a575c909df488e00a6f822d8ba8cb3ec65b45526215d2341b0bc61795c6627，旧preHash/验证器不变。AR2最终1951扫描/192分类/93迁移，五类错误空（/tmp/sc4-e5a-final-closure.log）；编译、diff检查、memory validate GREEN。原文档和Playwright依赖改动保护；不push，230 L0挂起。

下一波e5b补当前会话的原Task/Run事务转换与统一AnalysisRuntimeReceipt，e5c已提交只读核对/未知结果/原路径回归；具体接口和验证先更新原方案，再编码。之后e6原初始化起点加完整十二源组合、Outbox自然触发、主升级安装、真实首链/八场景/观察和发布判断。当前只有内部会话许可检查，不宣称恢复闭环完成。
