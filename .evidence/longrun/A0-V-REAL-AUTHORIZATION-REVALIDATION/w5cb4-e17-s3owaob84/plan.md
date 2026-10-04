# b84 严格写者响应与可信发行接续

Rules：上位231/b80/b83后续清单，m1单写、135真库只读、Scope与最小权限、Task/RED/最小修复/相邻验证/Delivery。基线39a2ba1d，authority1329。先实证已登记的提交后取响应风险，后续完整发行不能以连接/空服务替代。

本子任务精确改services/aos-api/aos_api/aip_production_contract_store.py的revoke_evidence_bundle末尾（若RED证实，先同事务get/验证DTO再commit并return）；services/aos-api/tests/aip/test_aip_license_source_authority_pg.py新增真实NOSUPER/NOINHERIT/NOBYPASS独立LOGIN私有临时passfile测试，复用b81安全fixture/连接准入且仅测试patch自有role。只给该随机role业务所需SELECT、event/Receipt INSERT、受限source lock EXECUTE与scope policies，无aos_runtime成员/无head写/无发行权。finally清自建policy，再原fixture清自身role/私有文件，不能更改既有roles。

RED预期：first revoke commit成功后SET LOCAL tenant已清，严格role第二个get被RLS隐藏，返回NotFound而event/head/Receipt已1/1/1。这是未知响应风险，不重发：先独立只读snapshot对账。修复前构造响应要在commit之前，任何响应解析异常必须整事务rollback；same-key replay不额外写。role positive+同键重放/canary读隔离与原b83并发/rollback/API累计；保持原响应/Receipt/hash，当前真库不DDL、不Provider/商城源。

后续发行必须继续Owner/policy原始权威映射、独立issuer身份/完整事务受限写/原source canonical验证及真实PG positive，不能从本随机写者冒充正式evaluator或发行许可。本子任务不宣布b84整体发行已完成。Scope未损失不得凭静态猜测改生产代码。
