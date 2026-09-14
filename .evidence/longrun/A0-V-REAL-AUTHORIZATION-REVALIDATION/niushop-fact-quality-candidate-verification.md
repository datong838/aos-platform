# Niushop逐事实字段候选验证

### SC4-5k2 Niushop 1.20字段候选验证

新增1.20仅版本/eval/fact-quality.v1.json，冻结1.19与12映射/原cohort/关系/用途质量策略字节不变。新树sha256:0a5d0b369f701e5aee68d5b3692fc0b6a89b1d89d195ccd4b549f7388d5a423b，字段策略sha256:79c6a340984fb2e3b2e4cd918476da5378a70ca06c2ae00b771bdaebd0ba697d。全部字段在实际public projection或公开映射，CustomerLite无PII、Shipment无跟踪号要求、未付款Payment无payTime要求。

Order.payStatus与Review.score仅非负整数字段结构检查，不解释未知业务枚举/分值含义；记录ACTIVE不代表成交/签收。数量新增严格positive-integer拒绝0或字符串；旧predicate行为不变。Red2失败/23通过4.75秒，Green新25+原关联18/业务cohort18/正式quality25=86 passed/4.63秒（8warnings）。候选静态7检查及原14关系/5用途/6cohort检查通过；重复prepare在目标存在门拒绝，未覆盖。AR2扫描1933/188/93五类错误为空。

没有构建签名、发布、安装、源读取、主库修改或正式Fulfillment；静态完整行是构造fixture，未声称真实12类字段全合格，金额对账/跨字段一致性/业务解释仍由后续事实与查询规则负责。

下一波SC4-5k3：在原business cohort当前事务内读取SnapshotFactQualityPolicy安装导出，核exact ref/hash/purpose/两前置策略hash，完整原snapshot rows执行计量，绑定真实requirement与上下文hash，消费前后重读策略并校验载荷；沿用原pending/source守卫。仅计数输入不直接签发quality pass，后续原QueryResult/QualityEvidence及Outbox消费者和主环境切换仍待完成。
