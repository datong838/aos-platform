# 逐事实联合字段计量验证

### SC4-5k1 逐事实联合字段计量验证

新增pipeline_snapshot_fact_quality.py，显式绑定cohort/relationshipQuality/purpose，每对象一组非空必需字段，固定7类严格谓词。执行复用完整cohort/关系校验与原选择器；每行所有必需字段及required关系联合成立且非unknown才有效，disclose关联仅诊断；各fact独立observed/eligible/valid/excluded/duplicate计数，空分母仍零，不跨类合并population。数值不接受bool/NaN/Infinity、身份不接受非规范前导零、时间不接受无时区/非正Unix/晚于观察。原raw不改。

原关系计量仅抽取reference_row_issues共用函数，allowedUnset/缺引用/坏引用/缺父/删除父的旧计数语义保留。Red模块不存在，初轮81 passed/5.28秒；增加互补坏字段不能平均、required/disclose用途差异后84 passed/5.38秒（8warnings），覆盖新23项及原关系18/业务cohort18/正式quality25。AR2扫描1933/188/93，五类错误为空。无主库/源读取/安装/模型调用。

下一波SC4-5k2：复核12映射的实际公开字段和业务含义，为Niushop新增版本化逐事实字段策略候选（预计1.20）；CustomerLite/Payment按public_projection，不要求已脱敏PII；金额/支付状态/商品上下架区分，Shipment跟踪号脱敏占位不能冒充真实物流信息，Review维度不冒充近30日评价。具体字段不能为通过而删改，旧initial_store_analysis阈值不动，空事实仍需原正式规则处理。随后把字段策略接入当前Owner及QueryResult/QualityEvidence/原Outbox消费者，主环境迁移安装和真实首链/八场景尚待完成。
