# UQ3-C 原宿主数据库角色验证

2026-09-13，基线d35035a2。a0v_033新增独立宿主principal函数，限定aos_runtime、非超级session、当前scope/subject、REPEATABLE READ/SERIALIZABLE；成员及markings锁不依赖成员表UPDATE。宿主仅获请求状态/claim/结果列UPDATE，原trigger继续约束状态/Attempt/immutable身份。

9 passed、7项既有warning：真实非超级宿主账号current principal→claim→complete，原Attempt同终态；成员UPDATE、subject/target/deadline修改、DELETE/INSERT拒绝；API角色不可调用宿主函数；READ COMMITTED宿主拒绝；成员撤销阻塞到锁事务结束。首次9项因临时schema未授宿主USAGE而未到达目标检查，修复测试schema权限后重跑通过。

未迁移主库。下一波快照读取切换宿主受限principal函数，保持同事务权限与canonical数据；再接具体消费者和原PreparedJob。此处成功结果{}仅账本测试，不是业务验收。
