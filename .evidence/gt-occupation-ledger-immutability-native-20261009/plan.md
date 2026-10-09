# 已有占用根/首事件的不可变完整性验证

复习231、AOS-001615交付及actual-admission-investigation。候选一：账本生命周期前置不可变验证，依现有可信Target call/root/event；候选二Judge类型证明/父预算费用authority细化，依独立价格事实且保留null价格。先选一，产品不修改。

精确测试目录 `/Users/ddt/work/projects/ai_agent/aos-platform/.evidence/gt-occupation-ledger-immutability-native-20261009`。全新独立原生库、原Source/SCRAM/正式双批准/四腿计划/Target Intent/call/root/event。在该库临时Owner窄探针直接UPDATE/DELETE已有根和首事件，预期原immutable trigger42501；pending deferred event时TRUNCATE预期PG55006，空表TRUNCATE独立证原no_truncate42501；每次savepoint回滚后精确readback不变。临时探针固定SQL/revokePUBLIC/fixedsearch_path/原NOLOGIN Owner，仅隔离库，结束清理并独立回读。

不重复上轮10项runtimeDML和两专门提交门，不扩大真实Judge50秒有效期；全原生节点仍完整回归，实际COMMIT拒绝和六表零/Source1/原资源保留独立验证。不启实际准入/状态转换/费用/transport，不动默认迁移与真库。纯测试已通过且产品不变，无新增重复累计必要。浏览器不适用于未接运行入口工件。

R1失败20.42秒：根表单独TRUNCATE先由引用外键0A000拒绝，尚未进入自定义触发器。独立六表零/临时探针零。R2仅改测试窄根截断探针为明确两表TRUNCATE（不使用CASCADE），验证根触发器42501；已有行pending门55006，事件表独立验证。产品不变，原有效期不变。
