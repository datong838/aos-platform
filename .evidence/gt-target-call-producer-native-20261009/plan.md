# 接续实现设计：窄Target调用准备producer

沿1612登记计划，拟修改唯一产品文件 `/Users/ddt/work/projects/ai_agent/aos-platform/services/aos-api/aos_api/aip_physical_capacity_occupation_authority.py`，追加显式SQL artifact，默认migration不安装。

接口拟定 `public.prepare_capacity_target_call(bytea,jsonb,uuid,uuid,uuid)`，分别原Source packet/ref、完整plan、原Target Intent和call唯一ID。公开运行身份不能提交费用、配额、输入hash、容量或finalized标志。返回prepared_only与executionAllowed=false。

服务端读取同租户、同session_user/xid/pid的private plan/Intent/Input-binding/debit。每件重新计算canonical SHA匹配存储hash；Intent内debit/caseBinding及hash必须精确匹配原行。Target request/hash/application/parent必须对应plan的originalFacts.target。原case完整值须对应原Suite；inputHash须匹配原Intent、binding及case.inputArtifact，Judge不能借Target hash。

由plan原两parent/request/hash再调用已有capacity_occupation_plan_risk_fact，从原Source签名、批准、费用规则、current suite和三bucket重新读权威，比较去checkedAt后的facts，不凭计划快照独自授信。physical_account_id/token_upper_bound从当前fact派生，不能信客户端或旧任意准备量。写后同样复核，精确同call重放成功、同Intent/case不同call拒绝、不存在/跨租户/当前Source或申请漂移拒绝。

新表行仅可信准备态，不修改旧parent held约束，不更新物理并发计数，不重复计旧prepared_debit；继续不可合法COMMIT。完整风险分配、actual occupation、unknown持有、最终期限和executor仍单独待实现。原生测试必须实际插入正向call行，保存点覆盖所有负例、实际COMMIT拒绝、独立连接零残留；仅catalog CHECK/纯单测不能作正向producer证据。
