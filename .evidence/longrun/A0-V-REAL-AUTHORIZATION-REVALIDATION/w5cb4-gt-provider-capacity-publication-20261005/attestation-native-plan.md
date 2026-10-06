# S17/S18供应商证明完整原文typed SQL

基线AOS-001401/m1@3e1db751，复习231完整Source及原SupplierCapacityAttestation/token models、S17-S19合同。候选一：供应商证明完整typed原文数据库接受域；候选二：独立root/permit注册及实际签发COMMIT，需152与提交时钟合同。先第一项，完整16字段，不偷换可信签名/授权。

publication_store.py、test_provider_capacity_publication_pg.py及本目录，沿现publication Task/Lease。复用原read_signed_body、read_identifier、read_signed_time，新增read_supplier_attestation(bytea)。恰schema/tenant/asset/revision/publisher/key/supplier/validity/purpose/fingerprint/providers/evidence/maxConcurrency/tokenLimit/observedAt，positive scope/schema1/固定purpose；正整revision<=4300位；原identifier/fingerprint、Provider数组1..1000唯一assetID，完整4字段exactrefs，Provider/Evidence种类正确。token两种模式严格完整3/5字段、unit token、maxTokens1..1e12；fixed window seconds1..86400及aware anchor。并发1..1e6，aware递增窗口<=366日；observedAt<validUntil，允许早于validFrom，不能加原模型没有的时效约束。观察当前性属于policy/current授权下游门。

先缺入口RED；原parse_signed_capacity_body对照原生SQL完整合法与单项负例；两mode/bounds/Unicode/nonUTC/1000refs正向，NULL/catalog/超长整数负向。固定network-none r4 BEGIN临时私有schema/functions，ROLLBACK无持久DDL；publication/Source合同相邻、源码/方案复核、精确提交及上下文同步。无真库/Provider/服务变化，不完成原Task或Goal。
