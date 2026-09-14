# 不可变关系准备 journal 验证

SC4-5g8：a0v046 隔离 schema 与 PipelineSnapshotGroupRelationshipJournal 完成。原 input exact manifest 外键、严格 payload/时间/策略绑定、counts/link 形状、8 MiB 界限、tenant RLS FORCE 与不可变历史；准备在原 AssessmentOwner 同步回调及保存点内，原事务提交由调用方确认。

48 项隔离 PG 组合测试通过，20.84 秒。首次迁移 SQL JSON 常量被 SQLAlchemy 识别为参数，改为 jsonb_build_object 后完整 head 迁移及测试通过。格式合法但虚假 counts 的记录，当前 Owner 重算后拒绝；外层回滚、捕获后置发行否决均无准备残留，精确重放不增加源调用。

AR2 ar2-7 扫描 1919 模块，五类错误为空。主库仍未迁移，关系未应用，无正式 Fulfillment。代码 head 为 a0v046，主库此前确认 a0v038 未改。来源发行资产仍为测试 fixture；准备记录不能当已应用 Receipt。

下一项：独立提交确认后按原 ConsistencyStore 应用原对象批次与关系，验证 Receipt 完整性、忽略项、失败恢复和旧关系处理，再接业务 Readiness。

