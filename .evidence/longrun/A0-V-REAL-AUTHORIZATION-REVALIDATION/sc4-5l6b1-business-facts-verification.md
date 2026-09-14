# SC4-5l6b1 验证

基线e6bedf99；m1串行；不push；230 L0挂起。

### SC4-5l6b1 可配置实际业务内容计算

新增pipeline_snapshot_business_facts.py：完整绑定fieldPolicy/purpose，各fact显式records或group-counts字段；复用原cohort/quality重算，不接未经定义的新计算。records完整保留范围内公开值与unknown/invalid标记，坏值null、未选字段不导出，sourceKeyHash只是稳定定位非匿名化/领域ref；group-counts仅离散字段，known/unknown分开。历史/删除仅报告排除计数与原因，1000记录/256组/2MB超限拒绝不截断。无金额求和/成交/利润推断，factIds=[]，源认证与正式Evidence另由原当前Owner。

Red模块不存在；首轮55 passed/9.92秒，追加500条长公开文本超2MB与257分组拒绝后，新14+原field25+原cohort18共57 passed/8.06秒，7既有warnings。AR2扫描1939/188/93五类错误空；memory status强CURRENT/validate GREEN。纯计算，无数据库/源/模型动作。更正l6a描述：实际1.20的p11 mapping与关系/field策略均ProductReview，和SourceReadiness目录一致，早先Review简称不是命名漂移证据，已修正文档。

下一波l6b2：在新1.21候选包声明12类业务内容字段，继承1.20全部既有mapping/策略字节。Shop/Product/SKU/Category等记录选公开字段，Order/Shipment/CustomerLite/Payment按明确状态分组，不导出订单号、交易号、会员键、系统配置值或评价正文；OrderLine可读商品/数量但不加总当成交，ProductReview仅状态/分值分组不解释量表。候选先确定性编译/eval/重复拒绝，随后l6b3原当前Source/Query/Quality Owner落业务Evidence。候选不是已安装版本；自动续跑/主环境真实首链与八场景仍待完成。
