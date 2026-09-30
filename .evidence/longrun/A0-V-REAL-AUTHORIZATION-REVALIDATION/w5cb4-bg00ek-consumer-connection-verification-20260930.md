# BG00EK 独立消费者连接验证

基线AOS-000999/m1@3a165e9b。只改新增connection模块、PG测试及方案/本证据；无UI或HTTP入口变化，无需本波浏览器验收。当前真实库只读回读aos_current_preview_20260927|a0v_118，退出0。

## 实现与复审

- 固定caller独立登录，不切runtime、不回退通用DSN；只读预检匹配库/tenant/角色/成员关系/对象所有权/列级ACL/固定函数属性与EXECUTE。
- 精确loopback目标、0700父目录/0600非空普通passfile同uid检查，连接前重验；拒绝常见PG环境凭据/配置覆盖。OS独立用户/扩展ACL/HBA正式部署门尚未完成；文件权限检查不是正式隔离证明。
- 每连接单事务scope，超时有界，异常脱敏、无自动重试。调用方手工commit后scope失效，必须新建合法连接，不能悄悄延用旧授权。
- 真实TCP一次性PG工厂完成Producer/独立Issuer→消费→Receipt重读；测试临时LOGIN/随机密码均finally恢复NOLOGIN/NULL，临时passfile清除；不修改HBA，不声称正式鉴权。
- 真事务失败回滚，已有head从revision1→2合法批准消费，旧Receipt重读保持head2。
- 最终写入时效测试在隔离库创建临时AFTER INSERT Receipt等待触发器，pg_stat_activity观察advisory锁后跨批准期限释放；原SQL返回NETWORK_CONSUMER_EXPIRED，head/revision/Receipt全0。触发器仅制造延迟，无替换时间或审批逻辑，finally删除。

## 验证记录

模块缺失RED退出2；配置/工厂缺失8 failed退出1。专项18 passed，随后真实工厂/回滚/作用域等累计65 passed/35.31s；新增head修订专项1 passed/5.49s，最终写入到期专项1 passed/9.11s。

最终累计命令（repo root）：
`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_consumer_connection_pg.py services/aos-api/tests/aip/test_network_atomic_consumer_pg.py services/aos-api/tests/aip/test_network_consumer_boundary_pg.py services/aos-api/tests/aip/test_network_approval_precheck_expiry_pg.py services/aos-api/tests/aip/test_aip_network_policy_action_producer.py --tb=short --show-capture=no`

## 剩余与下一波

当前库118，代码120未部署；正式caller/checker/issuer、真实Egress、八配置/Host/自然首链仍pending。未知事务结果必须只读对账；现有consumer无表SELECT，消费函数起始FOR UPDATE亦不能在read-only事务用作对账。下一波BG00EL先设计固定scope/Proposal/Event的只读Receipt对账权威，不给caller任意表权限，不借重试消费假装对账；随后连接正式服务。迁移仍须独立一致备份/克隆全链/零执行波。m1单写、不push、旧12Run/商城源/手工run_definition/230 L0均不触碰。

最终累计句柄90877退出0：67 passed / 7既有warnings / 39.77s；git diff --check退出0。第6/9步复审通过，进入精确提交与Delivery/authority收口；正式部署与自然首链未完成。
