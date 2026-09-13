# 当前 UI 主体事务读取验证

基线 90620186。独立只读当前成员事实接点，严格 scope/subject/required markings；本地 PG 精确单行角色与标记 FOR SHARE，不写成员、不授予角色、不返回 executable。远程 OpenFGA 配置时拒绝使用本地替代权威。

22 项测试通过，包含真实隔离 PG 两连接锁测试：当前事务期间删除成员与标记均触发 lock timeout；事务后撤销成员，下一读取立即拒绝。其余覆盖 scope、成员缺失/重复、marking、无事务、远程模式及原 UI target 门禁。ar2-7 1836/161/93，五类错误为空，diff --check 通过。

这是后续事务内 UI 权限复核的事实来源，尚未接业务执行，不作为命令授权。下一波部署已完成的只读目录 API 做真实安装/负租户读回，再继续事务内签名声明与 caller 权限接线。主库业务数据、账号角色、九项 dispatch fence 未改。
