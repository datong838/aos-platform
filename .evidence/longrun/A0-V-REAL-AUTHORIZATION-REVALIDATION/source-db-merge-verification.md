# 数据库合并与回读验证

基线10ddaefe。persist_source新增可选merge_existing/replace_fields，既有默认替换不变；登记只传本次显式字段，不再传旧cache配置。ON CONFLICT在数据库当前props上删除指定认证字段/合并，类型不一致拒绝，RETURNING结果作为缓存与公开响应来源。

执行隔离PG及两专项共23 passed（1PG组合+22单元）；git diff --check通过。PG包含保存配置→元数据保留→认证轮换→再次元数据保留→异type拒绝→canary无凭据。初次PG因LIKE不复制配置版本触发器导致configuration_revision NOT NULL失败；fixture增加随机UUID默认值后通过，这只是隔离merge SQL验证，不是配置版本触发器/历史链验证。未改public、未读取真实源，无Provider调用。

修复范围为metadata原子合并与权威回读。显式config并发更新仍是最后写入者生效，尚未expected revision CAS；版本触发器PG组合与浏览器流程继续下一步。原接口测试的数据库mock已改为返回保存结果，元数据请求断言不携带旧缓存密码。

旧schema/pytest警告保留。本轮未进行红阶段产品失败复现，前轮已证明旧缓存丢配置。前轮Receipt的HEAD对应固定10ddaefe，本文及新Receipt作明确补充；不修改历史事件。不push，230 L0挂起，完整首链/八工作台未完成。
