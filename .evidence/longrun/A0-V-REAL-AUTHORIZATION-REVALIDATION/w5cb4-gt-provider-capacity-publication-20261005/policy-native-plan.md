# S17 完整来源policy原文typed数据库合同

基线AOS-001400 / m1@79228309；按231完整Source和sql-approval-equivalence S17。已登记候选：完整policy typed SQL（本轮）、独立可信root/permit注册与真实COMMIT（需独立152及时间合同）。本轮不把shape当签名/来源可信或完整Source。

文件 services/aos-api/aos_api/aip_provider_capacity_publication_store.py、services/aos-api/tests/aip/test_provider_capacity_publication_pg.py及本目录，沿publication原Task/Lease。复用read_signed_body/identifier/time/deployment_target，新增read_source_policy(bytea)，完整17字段与ProviderCapacitySourcePolicy+parse_signed_capacity_body接受域一致。恰双正向tenant/schema1/固定publisher及purpose、正整revision<=4300位、各原identifier、root sha256、年龄1..86400/偏差0..60、唯一允许模式数组1..2、完整deployment及aware递增窗口<=366日。必须先原始canonical bytes解析，返回JSONB仅作字段视图。

先新常量缺失RED；原模型完整合法文档逐项变异，同时原parser和原生SQL拒绝；合法最大/最小整数、两种模式组合、Unicode和非UTC微秒边界roundtrip。SQL NULL/错误shape和pg_proc INVOKER/IMMUTABLE/nonSTRICT/fixed search_path/noPUBLIC验收。固定无网络r4测试容器BEGIN创建私有纯计算函数，ROLLBACK，无持久DDL。publication+Source合同相邻、源码/方案复核、精确提交/Authority和Prime同步。无真库/服务/Provider，无原Task Delivery，完整可信来源/签名发行消费者及自然首链仍pending。
