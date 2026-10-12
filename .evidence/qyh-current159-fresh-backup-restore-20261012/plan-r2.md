# 当前真实159独立完整恢复 r2

Rules231/已授权栖月汇恢复、原ACTIVE Task/Lease。原双备份SHA da795fb61c7a2ccdee1404949b0b6be21c39735655b8cd6fde2f7718c9aec815 与647表指纹保留；前次exact bootstrap恢复明确磁盘满/单事务回滚、旧目标aos_meta_head表0。独立容量维护已经60GiB，真实卷/cluster/647表无变化，原exact restore卷容器同CID恢复，原角色/GRANTED BY已导入。

本轮新增restore-r2.py及r2 intent/terminal/verification在本Task evidence目录，仅创建新DB qyh_current159_full_restore_r2_20261012，network-none原exact镜像实验容器qyh-current159-exact-restore-20261012；不重放旧attempt、不覆盖旧失败DB/日志，不改真实源/Host/worker/Provider。新意图独占先落盘，原双copy SHA/源647指纹/空目标状态核验后原pg_restore单事务exit-on-error、replica仅该子进程防业务trigger，完整原owner/ACL保留。

恢复后专项为647表行数/SHA全相等；相邻为pg_dump schema-only完整SQL规范化比较（仅移除原pg_dump随机restrict/unrestrict token行，其他不掩盖）、所有用户sequence值/is_called和完整非系统角色flags/成员关系grantor对照。源before/after再读必须相等。原结构SQL/日志private0600，无业务数据出日志/提交。失败保存terminal/只读回滚结果，未知不重试。schema/权限/序列未全过不Delivery、更不能迁移真实库；成功也不证明正式登录、发布/安装配置/八页面或自然经营首链。
