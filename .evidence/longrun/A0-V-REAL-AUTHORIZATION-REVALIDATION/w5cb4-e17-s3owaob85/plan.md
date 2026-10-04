# b85 原始canonical输入存证实施方案

上位231/231-4/栖月汇经营执行方案/b80完整evaluator方案/b84登记清单。基线ce16ca24，authority1329强CURRENT。m1唯一写者；135真库只读，不授正式角色/Owner/Policy/Host/Provider权。保留现有server build coverage与canonical_hash算法，存证不是License或start授权。

## 精确文件
services/aos-api/alembic/versions/a0v_138_evidence_build_provenance.py 新append-only表，down137，精确Evidence租户/revision/hash FK、build operation/key Receipt FK，无backfill，无downgrade删历史；runtime仅scope SELECT/INSERT，PUBLIC无权，UPDATE/DELETE/TRUNCATE均旧55000guard。
services/aos-api/aos_api/evidence_bundle_provenance.py 新caller事务读取验证；复用旧canonical_hash，不复制算法。requiredFactIds及全部输入DTO规范、authority计算结果、原row字段/时间语义、原request_hash/result_ref一致检查。无存证/错scope/错hash/Receipt漂移拒绝。读取不是发行/许可证/可执行权限。
services/aos-api/aos_api/aip_production_contract_store.py 新build完成两个Receipt后同事务写存证；原hash/result/DTO不变，同keyreplay不补写历史、不重计算。旧135/136/137无存证表保持generic build兼容，显式存证读取fail-closed；新表已存在但缺权/错误不得fallback。响应构造先commit，异常完整回滚。
services/aos-api/tests/aip/test_evidence_bundle_provenance_pg.py 真PG RED/positive/原hash再现/两种requiredFactIds同旧行/hash异/双别名重放/故障回滚/错hash/旧无存证拒绝/ACL+scope/maintenance不可变/Receipt和row漂移。
services/aos-api/tests/test_w2a_production_contract_store.py 与test_w2a_production_contract_api.py 旧清理删除父记录会破坏append-only来源历史；UUID隔离、仅一次性库断言、保留session历史，最终原session fixture DROP自有DB；不得禁trigger/删存证/改业务测试断言。

## 验收/风险
先真实build后查缺表RED；最小实现后PG读回旧hash/required输入，与computed server authority相符。注入存证失败确认bundle/两Receipt/provenance整体0，幂等重放不变。独立角色runtime的scope读/写、跨tenant/noscope拒、父FK及不可变检查。原W2A/B Store/API+b81–84累计，signed全schema按实际head；必要135兼容测试仅自有隔离库。每测试session结束检查test DB/本轮新增NOLOGINowner，安全attrs/成员/依赖0再清自建role。无页面变化无需浏览器冒充业务验收。

输入与server计算结果的canonical存证仍不等于有权发行；正式issuer必须另外验证Owner/Policy/当前signed安装与来源准入，拒旧缺存证。存证保留PII风险：仅原build请求与既有覆盖诊断，不读取原商城/不新增Evidence payload/secret。已有Evidence refs失效仍需当前source核验，历史hash不代表fresh。后续必须接完整发行与八维命令，不以本存证交付宣称首链。
