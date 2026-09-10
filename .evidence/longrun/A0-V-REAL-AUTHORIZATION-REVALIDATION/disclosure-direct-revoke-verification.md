# EvidenceDisclosure 直接撤销验证

基线c25ce359。先补方案，再写7项专项测试；修复前7 failed（未查撤销、查询异常未传播），修复后7 passed。命令：AOS_DOTENV_DISABLED=1 AOS_TEST_USE_SHARED_DATABASE=1 services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/aip/test_evidence_disclosure_direct_revoke.py -q --tb=short。git diff --check通过。

L1/L2/L3各自覆盖有效与直接撤销对照；撤销时无grantedLevel、displayPayload、expiresAt，bodyReturned=false。SQL显式绑定org/project/evidence/revision/hash；查询异常传播，不降级放行。resolve和enforce_current_policy复用同一_evaluate_disclosure，未改变有效来源正常披露规则。

测试采用合成连接和数据，未执行PG、真实数据或Provider验证，不证明实际RLS或并发撤销序列。已有7项启动警告和JDBC退出日志closed stream问题仍在；不是本次新增或已解决项。

方案一致性：仅补缺失的直接撤销判定，无迁移、无业务数据改写、无页面或源抓取。下一步继续L3 source materializer，必须绑定original request/actor/租户/exact Evidence/有效期，并在读取边界处理撤销竞态，再接真实上下文。当前完整首链仍未运行，八工作台和连续观察均未完成。不push，230 L0挂起。
