# b84 撤销响应事务验收

严格随机 LOGIN/NOSUPER/NOINHERIT/NOBYPASS 角色、私有临时连接配置与最小业务ACL实证：原实现先提交后读取响应，SET LOCAL scope清除，RLS导致ProductionContractNotFound；独立只读对账epoch/event/Receipt=1/1/1，未重发。有效RED见strict-role-red-valid-fixture.log，1 failed，4.76s。

首次夹具收尾未结束只读事务，DROP POLICY被自身admin锁阻塞。精确核对一次性测试库aos_test_7a0cacaaf122_ti4_test与idle PID167819后仅终止该连接；原失败日志186.06s含teardown错误，不能作为完整业务RED。finally先admin.rollback修复夹具，第二次RED正常收尾。

最小生产修改：revoke_evidence_bundle在原事务内读取并构造结果，成功后commit返回。响应验证注入异常时，caller内见1/1/1，外部回读0/0/0。严格角色首次响应、同键重放、canary隔离通过；不扩大发行/表写/身份权。

累计七组真实PG/Store/API测试：78 passed，8 warnings，48.45s（green.log）。两文件py_compile与git diff --check通过。方案与实现一致，仅响应顺序改变，既有Receipt/hash/幂等路径保持。没有重新运行真实安装或业务首链。

清理：测试库数量49；本轮初始为0的fence owner在所有测试结束后确认安全属性、双向成员0、共享依赖0，才删除本轮角色；最终角色0、测试库49。历史库/角色、用户改动与真实135未改。

后续真实缺口：原build canonical payload包含requiredFactIds，旧Evidence持久化行未保存该输入，Receipt也仅保存request_hash/result_ref。不能从现有行猜测requiredFactIds或以另一个摘要冒充原contentHash。下一安全方案应保留原服务端canonical构建输入与结果的不可变同事务provenance，再闭合Owner/policy原始授权和正式发行；旧无provenance行不得自动升权。当前来源fact仍NO_START，完整发行、八维事务及自然经营首链未完成。
