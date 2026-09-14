## SC4-5l6e5b2b 快照统一Host与Receipt（2026-09-15）

基线bf3364a4，m1/AOS-000573。先完善snapshot-resume-design.md，再修改ecommerce_analysis_snapshot_resume.py、ecommerce_growth_runtime_adapters.py、ecommerce_growth_host_composition.py，新增test_analysis_snapshot_unified_receipt_pg.py并补会话注册表测试。Session.resume在原current stage与原Origin/current dispatch内通过专属exact注册表进入原LockedHostPort，TransactionBoundConnectFactory阻止提前commit；原_resume_states转换后重读原Task/Run/Compilation/控制Receipt与domain Receipt，生成原统一AnalysisRuntimeReceipt，mappingRef仅快照模式为null，原_HostAnalysisReceiptStore保存并精确回读，原Adapter/BoundStore journal同一身份。

普通Host解析和Adapter分析journal解析默认仍是旧strict，新快照仅exact内部Host/Adapter覆盖；普通注册表拒绝快照、非active会话拒绝调用、bool/任意Host不接受。原prior精确恢复分支支持快照，但原_strict_analysis_command不放开；旧水合字段保持。

Red缺少Session.resume（1失败6.43s，/tmp/sc4-e5b2b-red.log）。18432隔离PG 4 passed /10.46s（/tmp/sc4-e5b2b-green.log），使用实际原初始化Task/Run、Origin/当前dispatch/LockedHostPort/统一Store，整个快照交付stage仍named：统一回执可按原key和exact ref读回，Task/Run各+1，mappingRef null且无模型步骤；保存失败、回读篡改、外层Origin后验失败时Task、Run和统一回执整体回滚。138项快照/会话/原分析/恢复合同回归通过4.93s（/tmp/sc4-e5b2b-regression.log），另4项旧恢复PG通过10.14s（/tmp/sc4-e5b2b-old-pg.log）。均7项既有warnings。

AR2 1951/192/93错误列表空（/tmp/sc4-e5b2b-closure.log）；编译/diff、memory validate通过。主库未升级、没有真实商城读取/Provider执行/发布安装，不push，230 L0挂起，用户原改动保留。首次统一提交接口完成并不表示重启恢复或真实十二源首链完成。

下一波e5c：原Scope/Origin/current dispatch下先读原统一Receipt，已有提交只核对严格命令hash、实际原Task/Run/control/domain/统一结果，不重新进入paused阶段或新造执行许可；缺统一Receipt但有原控制/domain转换痕迹时阻断重复提交，未知/已推进状态明确核对。再e6真实起点与完整十二源组合、Outbox自然消费、主升级安装、真实首链/八场景/连续观察后发布判断。继续自动接续。
