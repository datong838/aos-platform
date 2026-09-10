# 原接入命令不可变保存

基线1bc14586，按ingress-recovery-contract第一步。新增a0v_005迁移（前置a0v_004）、ec_ingress_journal.py及PG测试。持久化完整验证后的BatchCommand、run/pipeline、源id/配置UUID、pipeline hash和envelope hash，唯一scope/run。FK绑定已有源配置历史，禁止更新删除截断，运行角色只读/插入，RLS按org/project。仅内部Owner读命令，不暴露HTTP正文。

save同键同完整hash回读、异hash冲突；命令scope/stream须一致，拒绝非JSON/超界类型，校验完整envelope hash后读取。hash包括原CAS值，存储不能修改重写，执行Owner自行核对既有Receipt。持久层不代表当前执行授权，不在本轮接executor或开启工作器。派生所需扩展输入与当前源绑定验证在后续装配前补齐，不能以只有BatchCommand宣称全流程可恢复。

PG测试新schema实际迁移，源配置历史用最小FK fixture（不复制凭据），保存/新连接读/重复/冲突/租户canary/不可变/非空降级拒绝。仅隔离测试库迁移，不改public现有表。
