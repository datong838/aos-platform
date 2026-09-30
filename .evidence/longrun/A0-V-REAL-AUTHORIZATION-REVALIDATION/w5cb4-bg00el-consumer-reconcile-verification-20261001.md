# BG00EL 只读Receipt对账验证

基线AOS-001000/m1@f2baac28。新增a0v121固定四参数只读STABLE SECURITY DEFINER函数及Python入口，无新增表授权；owner/固定search_path、独立caller/tenant、read-only在SQL强制，Python再校验函数属性/ACL/结果形状。Receipt requestHash/Proposal binding/resultRef/不可变revision hash联合核验；已观察历史提交不依赖当前head或批准仍有效。

## 验证

缺模块RED退出2；核心真实PG4 passed；最终六组累计命令（repo root）：
`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_consumer_reconcile_pg.py services/aos-api/tests/aip/test_network_consumer_connection_pg.py services/aos-api/tests/aip/test_network_atomic_consumer_pg.py services/aos-api/tests/aip/test_network_consumer_boundary_pg.py services/aos-api/tests/aip/test_network_approval_precheck_expiry_pg.py services/aos-api/tests/aip/test_aip_network_policy_action_producer.py --tb=short --show-capture=no`

句柄54838终态：76 passed / 7既有warnings / 44.96s / exit0。覆盖未消费无副作用、已提交精确Receipt、回滚未找到、错Event冲突、跨租户不可见、SQL自身拒绝读写事务/错scope、runtime/issuer无EXECUTE；持有Proposal FOR UPDATE时1秒内读回成功；批准到期及checker移除不抹去历史Receipt。相邻原子消费、真实TCP工厂、权限、期限、Producer继续通过。

复审：函数仅SELECT且STABLE，无动态SQL/行锁/写入，不给caller表SELECT；未找到绝不触发消费，返回无重发许可。无HTTP/UI改动，浏览器不适用于本内部切片。git diff --check退出0。

当前真实库只读查询退出0：aos_current_preview_20260927|a0v_118；代码121未部署。当前批准/八配置/Owner/Host/自然首链均未完成，隔离身份不是正式业务授权。未知结果仅读对账，unresolved不能被解释为重发许可。

下一波BG00EM：复习独立issuer服务命令/OIDC与消费者正式调用方合同，冻结精确消费/对账请求和权限边界，再实现独立服务接线；不把caller凭据放回普通API。部署仍独立一致备份、克隆全链和零执行窗口，当前真实库只读。m1单写、不push、不读商城源、不重放旧12Run、不手工run_definition、230 L0挂起。
