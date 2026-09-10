# 原接入命令持久化验证

2026-09-11，基线1bc14586。新增a0v_005不可变命令表及内部IngressJournal，存完整BatchCommand与run/pipeline/source配置引用，完整envelope hash含原CAS。命令scope与stream必须匹配；8MiB上限，不自动提交调用者事务。

首次未开启PG opt-in仅skip，不作通过；正确隔离PG运行先因模块缺失红，实现后1项组合通过：实际迁移空表升降/重升、源FK fixture、保存、新连接回读、幂等、冲突、canary不可见、所有者删除被trigger拒绝、非空降级拒绝。diff --check通过。测试使用colima-aos-extension专用恢复PG随机schema，不改public；既有启动警告仍在。

限制：源历史用最小FK fixture，不证明生产权限或当前源配置可执行；仅存规范命令，尚未保存派生辅助输入、绑定现行run authority或接executor/work器。没有HTTP正文入口。当前FK是历史存在性，不是现行授权判定，接入执行前仍须复验。API/public schema未应用本轮迁移。全首链/八工作台未完成，不push，230 L0挂起。
