# D01/D02 模型结果合同施工

2026-09-11，基线e39c4a60，AOS-000573；m1单写、不push、230 L0挂起。

产品/技术依据：231-5/231-6真实画像→诊断→业务计划。InsightRevision强制metricRefs/methodRef/evalRef，DecisionSummaryRevision强制Insight及来源；不允许模型自行生成正式引用或把相关性升级为因果权威。

本波新增 services/aos-api/aos_api/ecommerce_analyst_analysis_proposal.py 和 services/aos-api/tests/test_ecommerce_analyst_analysis_proposal.py。仅严格解析两类不可信模型结果，不写DB、不调用Provider、不输出InsightRevision/DecisionSummaryRevision权威对象。

D01：summary、assumptions、uncertainty、metricIndices、sourceIndices。D02：conclusion、attributionPath（可读证据归纳而非内部思维链）、keyAssumptions、counterEvidence、alternativeExplanations、uncertainty、sourceIndices。字段长度对齐现有Owner合同；拒绝额外字段、空白、重复JSON键、非有限数字、类型强转、越界/重复索引、无来源与超128KiB输入。引用只用受信输入列表中的整数索引。D01 kind由后续服务端方法/评测判断，本波不允许模型填写kind，更不能自行声明causal_claim。

复用D03已存在的重复键/非有限数检查函数，保持旧格式字节和请求hash不变；不为了复用改写现有D03模块。可读归因文本不是因果证明。测试先红后绿并回归已有D03解析/权威合同。验收仅格式层，不称真实经营成功。

下一波：绑定具体已校验指标、方法、评测、Bundle正文及固定请求hash，再接原AgentRun/Artifact可信接收和正式Owner；真实源、职责配置、宿主调度仍待办。任何缺失正式依据显式阻断，不填假引用。
