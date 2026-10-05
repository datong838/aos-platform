# 完整恢复门实际验收

r4 terminal exit0，9.655s；原库只读 a0v_135，克隆独立context colima-aos-a0v-test-only、容器 aos-daily142-c07aa90b1958、卷 aos-daily142-c07aa90b1958-data，同名数据库不指向18435。完整备份4228767bytes、TOC5905、SHA c9457874da41590fddfc8fd2296991b90a79aac9aa68f5516d7bac0b4dcd7f20。私有资料目录 /Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261005-142-gate-tco9khl1；600文件、700目录，原始数据不提交。

实际592原表完整恢复前后精确一致；原角色属性/config摘要、成员/原grantor、有效表ACL/函数EXEC、RLS/函数定义/序列、数据库级权限/完整规范化ACL/属性/数据库角色设置摘要一致。原Alembic七步135→142逐步事务及版本回读成立；旧行不变，仅预定Source两metadata新增；五新表全空；三新role无LOGIN/成员/高权。源135再次全摘要不变；目标无网络/端口/源卷，所有旧演练资料保留。

r1真实bootstrap grantor错误、r2数据库ACL遗漏、r3ACL顺序差异均保留日志；r2窄GREEN已由plan明确撤销为完整门依据。r4完整比较证明顺序不同但规范化授权完全相同；17合同测试/0.21s，包含CONNECT及转授权扩大拒绝。无UI改动，浏览器不适用。当前真库迁移/服务重启/Host/Provider/商城源/业务执行未发生，不能据此宣称正式身份、八配置或自然首链。

本工具只覆盖public业务对象与原角色/数据库权限，不是其他数据库/整个主机灾备。正式当前迁移仍须独立Task、实际零执行窗口、停写一致新备份与再恢复、独立迁移门；本次在线只读演练不代替停写窗口。后续应先核实原8080/8434进程所有权与父进程，排除worker/Host/Provider及其他写者，明确停机与失败保留策略，再迁移；不降低schema startup guard。
