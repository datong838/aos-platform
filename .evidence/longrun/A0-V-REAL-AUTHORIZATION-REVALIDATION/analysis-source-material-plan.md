# 分析证据原文组装方案

2026-09-11，基线b034957f，AOS-000573；m1单写、不push、230 L0挂起。

依据231-5/231-6，D01/D02应消费当前任务的真实证据正文，不以引用或样本计数替代事实。本波新增 services/aos-api/aos_api/ecommerce_analyst_analysis_sources.py 和 services/aos-api/tests/test_ecommerce_analyst_analysis_sources.py。

受信入口接受调用方事务conn、scope、task_id、actor、严格Bundle exact及逐项原Disclosure decision/request、markings、aware now、明确source TTL及max_bytes。复用ProductionContractStore.get_evidence_bundle/get_brief和read_disclosed_evidence_source，不直接旁路读取正文，不新增授权或全局连接。

先校验同租户Bundle exact/frozen/complete/fresh/not revoked/cutoff窗口，以及当前frozen Brief exact且task_id匹配；逐项原授权必须purpose=source、L3、同Task，并与Bundle中的Evidence r1集合完整一一匹配。按Bundle item顺序读取，不依赖授权输入顺序。正文由原Owner校验原请求Receipt、actor、current policy、撤销/有效期和hash。全部成功才返回bundleRef、cutoffAt、items（evidenceRef/disclosureRef/expiresAt/payload），不返回部分材料；超调用方明确上限拒绝，不截断。

测试先红后绿，覆盖跨任务/权限/引用/缺项/重复/过期/撤销/超限；实际一次性完整PG中创建合成完整来源，原Disclosure Owner授权后组装，不调用模型、不在主库造业务。允许读取不代表允许发送给模型，后续仍需既有Executor出境及预算门。没有真实客户材料就不能声称真实分析完成。

下一入口：用这些材料构造固定D01/D02请求并绑定正式指标/Method/Eval与原attempt；可信结果接收Owner和三阶段宿主执行随后推进。真实源连接未变化不重试，230 L0挂起。
