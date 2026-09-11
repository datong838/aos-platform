# D01/D02 严格结果格式验证

2026-09-11；A0V-D01-D02-OUTPUT-CONTRACT-20260911；基线e39c4a60。

新增PortraitProposal/DiagnosisProposal与严格解析入口。模型只提供可读业务内容及受信库存的整数索引；不能提供kind/tenant/revision/hash/methodRef/approvedAt/reasoningChain。引用权威由后续接收服务绑定。现有D03模块不修改，复用其重复键与非有限数拒绝函数。

先执行测试得到新模块缺失错误；实现后新解析测试与既有D03 draft、analyst authority contracts共103 passed，7既有警告，退出0，0.16秒。覆盖合法回答、不确定性保留、额外权威字段拒绝、索引重复/越界/负值/布尔/字符串/浮点、无效库存计数、空白/强转内容、重复JSON键、过深嵌套、NaN、Markdown围栏、超128KiB和文本列表超限。

git diff --check通过；仅新增产品模块、专项测试和文档。无数据库读写、Provider调用、API重载或UI变化。JDBC退出清理closed-stream既有日志仍出现，未影响退出码。

限制：解析成功不是正式Insight/Decision，更不是事实/因果证明。未生成栖月汇真实画像、诊断或业务计划，未替代真实首链验收。

下一波：固定生成请求与原attempt绑定、真实指标/Method/Eval/Bundle引用核验及正文输入，再接可信Artifact接收与Owner；缺正式依据拒绝，不填假引用。宿主三阶段、真实运行配置/数据连接、自然首链、审批后内容续跑及八场景继续待办；不push，230 L0挂起。
