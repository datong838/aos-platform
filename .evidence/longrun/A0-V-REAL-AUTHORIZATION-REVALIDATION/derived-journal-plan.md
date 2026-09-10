# 派生命令关联原批次保存

基线af387877。新增a0v_006表ecommerce_ingress_derived_command，FK关联scope/run原批次；payload包含parent envelope hash与完整派生命令列表，支持空列表明确无派生。复用不可变trigger，RLS和只读/插入grant。非空降级拒绝。

扩展ec_ingress_journal.py保存/读取：验证父批次、每个派生identity/object_type是父批次非删除对象、stream相同、无重复对象、完整payload哈希。同键同内容返回，异内容冲突。读后返回原命令，禁止重新计算CAS/hash/idempotency。

PG测试实际迁移、新连接回读/重复/冲突/父对象不匹配拒绝/canary，保持旧不可变数据。只在隔离schema执行，不改public。该存储不证明原批次已提交或输入revision来源正确，后续执行装配必须核验base Receipt及当前授权。
