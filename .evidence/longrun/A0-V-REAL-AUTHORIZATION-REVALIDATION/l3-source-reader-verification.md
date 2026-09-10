# L3正文读取内部Owner验证

基线93768a1e。新增read_disclosed_evidence_source在原有ProductionContractStore内；无外部endpoint、无迁移、无真实数据/模型调用。原Receipt完整request_hash绑定task/subject，exact result_ref绑定decision；scope、actor、L3、purpose、expiry与Evidence均复验。读取前后共享policy检查，旧expiry不续期；返回完整payload和exact来源引用。

执行AOS_DOTENV_DISABLED=1 AOS_TEST_USE_SHARED_DATABASE=1 services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/aip/test_evidence_disclosed_source.py services/aos-api/tests/aip/test_evidence_disclosure_direct_revoke.py -q --tb=short，18 passed；git diff --check通过。新增11项覆盖完整正文、actor、task、receipt、expiry、level、status、hash和前后policy/expiry变化。使用合成连接；reader测试替换共享policy，邻接7项单独测试policy撤销逻辑。没有PG/RLS/并发验证。此次实现先于测试，未取得红阶段证据，不表述为完整TDD。

审查：无源URL抓取、无无租户读取、无新授权和自动续期；现有7项启动警告/JDBC关闭日志问题仍在。当前调用者须提供可信principal markings，方法未注册到runtime。多条查询不是并发撤销到发送的原子授权：模型发送前仍需重新验证当前authority，后续必须做PG及真实reader组合验证。Evidence hash沿用Owner持久hash，未发明payload重算规则。

首链真实输入还需从DataFulfillment/EvidenceBundle导航到正文并按实际数据字段提取，Host异步接续与生命周期仍未装配；八工作台、连续观察、发布评估未完成。下一步执行PG组合验证与来源字段核查。不push，230 L0挂起。
