# 正式Query证据生产与上游授权传递

2026-09-11，m1 9635082c，AOS-000573。延续D01查询绑定与技术15/160：QueryResult不是自行新增指标事实；Evidence必须有来源、许可、marking和撤销关系。

## 文件与路径

新增平台模块 `services/aos-api/aos_api/aip_metric_query_evidence.py`：内部同事务生产器，输入精确MetricDefinition/QueryResult、原始逐源L3请求与decisionId、同TaskRun/actor、now/大小限制。Owner读实际Query结果/原请求，验证同actor和租户、已完成metric查询、精确指标版本。只支持source_refs全部为原始Evidence r1且authority为postgres:aip_evidence，要求逐源完整有效L3；不将Dataset指针或unknown授权猜成许可。原始源不得再次为本派生类型，限制依赖深度。正式payload记录queryRequest、queryResult、metricDefinitionRef、sourceRequests、TaskRun/actor/marking和仅source用途许可；规范hash产生稳定Evidence ID，ON CONFLICT后读回核验全部列，撤销后不重新造新ID复活。不commit，由宿主事务/Receipt决定提交。

修改 `services/aos-api/aos_api/aip_production_contract_store.py` 的disclosure评估：仅新类型source_type触发平台生产器的来源复核；所有L1/L2/L3都必须保留原上游许可、actor、task与当前有效且原请求完全一致的decision有效期，任何上游撤销、变更、过期均拒绝。普通Evidence路径不变。防递归：读取父源前先确认类型不是派生QueryEvidence；原始source授权不重新申请，不提升许可。

新增 `services/aos-api/tests/test_aip_metric_query_evidence.py`：先拒绝测试、正式Query/Metric/Task/Disclosure Owner隔离PG组合；幂等、回滚、当前Metric漂移、源清册缺失/重复、源撤销和二次披露失效、跨scope、正文/列漂移、受控大小边界。现有Query绑定和披露回归。

## 限制和退出

本波仅内部生产器与公共披露集成，不增加路由/后台调度/主库写入/模型调用；自动宿主调用仍下一阶段。未支持的Dataset/其他来源拒绝并由数据需求补齐，不使用手工夹具作为业务成功。仅source用途许可来源于逐个实际L3 source授权，不宣称外部发布权。最大源数100、最大正文显式有界；源标记并集至少internal。验证后文档/清单/哈希证据和精确提交。不push，230 L0挂起，真实首链与八场景仍待完成。

## 审查修订：数据身份与短期授权分离

5分钟L3租期不能冻结为派生证据身份。生产时严格验证传入完整sourceGrants，payload仅保存稳定sourceRequests；再披露时在既有Production Receipt/Decision中读取same tenant/actor/requestHash、allowed且未过期的当前授权，并由原Owner再次检查原请求与实时策略。无有效授权即阻断，不自动申请。宿主显式续授权后正文/hash/证据ID不变，适配慢模型原请求恢复；撤销仍由当前Owner阻断。新增续授权同ID、过期到重授权恢复测试。
