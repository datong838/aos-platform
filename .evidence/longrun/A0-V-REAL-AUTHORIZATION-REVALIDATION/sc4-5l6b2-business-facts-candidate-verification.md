# SC4-5l6b2 静态候选验证

基线3540e48b；m1串行；不push；230 L0挂起。

### SC4-5l6b2 Niushop 1.21业务内容候选

新增prepare_niushop_business_facts_candidate.py及1.21.0，新增business-facts.v1.json；源1.20 tree hash保持sha256:0a5d0b369f701e5aee68d5b3692fc0b6a89b1d89d195ccd4b549f7388d5a423b，新tree sha256:33b35f7fb8dd145c4cd9700b71e396505ee1cd9cd669953a860c96304e5a2844，业务策略hash sha256:c35a535fb7852904c4ab07c7be6e0dc5d5c95af0c9e78a45ac4ba45d772d62d5。12类明确records/group-counts字段，排除订单/交易/会员标识、配置值和评价正文；商品标价非成交，分数不推断量表，渠道资料非能力健康证据。原mapping与全部既有策略字节不变；只更新bundle版本与bundle-evals，新添一个业务策略文件。

静态字段7项与业务内容7项通过，实际内容/原状态分组/未知窗口/坏值null/确定性均检查，未重跑对象写验收。重复执行在复制之前拒绝；再次核源/目标hash不变。AR2扫描1939/188/93五类错误空；memory strong CURRENT/validate GREEN。无source/DB/model/install/publish；OCI/SBOM继承数据不是新版本构建凭据，需正式build/sign阶段生成。未据静态fixture宣布真实链路。

下一波l6b3：原当前SourceEvidence守卫中加载安装的SnapshotBusinessFactPolicy并绑定同field/cohort/quality策略，完整原rows生成实际业务内容，保存类型化BusinessFact Evidence及精确当前回读。只对真正有内容并满足质量的事实声明覆盖，源/质量Evidence仍factIds空；unknown/empty/撤销/跨租户/策略变化拒绝或保留明确缺口。随后原EvidenceBundle新鲜度、Readiness、snapshot resume与Outbox仍按l6c-f推进；主环境升级与真实八场景未完成。
