# 栖月汇159持久化恢复预备
Rules AGENTS/AOS工程交付/231-4和历史恢复登记。原名称维护待批准；独立副本持久化已授权安全准备，选择后者。
从已验证159恢复tmpfs副本导出全库一致备份+globals无密码和第二校验副本；另建命名卷aos-qyh-history159-prepared-data-20261011和networknone/noports PG，不接原源卷，不替换当前库。精确镜像固定，完整pg_restore失败必须保留。647表全行指纹前后精确对账（含原历史及合法迁移新增）；数据库CONNECT ACL在独立目标精确恢复，源真库仍092完全不变。
每次create/restore前intent，未知结果只读对账不重发；保留所有源/卷/备份/容器，不读商城，不启动API/Host/worker/Provider。备份private0700/文件0600，git排除，角色密码不读不保存。
正式启动原profile固定preview库/approved安装/绑定0，必须单独正式历史恢复profile或显式审批窗口；不可env绕过，不能把持久化候选当正式库切换完成。输出部署方案和精确未完成项。

恢复647表指纹通过；继续完整roles/membership/databaseACL/schema/sequence对账，只在隔离目标恢复两个原transport CONNECT。任何新差异失败保留，不自动豁免。
