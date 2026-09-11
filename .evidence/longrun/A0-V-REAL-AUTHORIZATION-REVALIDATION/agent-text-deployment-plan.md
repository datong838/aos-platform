# a0v_012实际恢复环境部署

代码基线d9707de0。m1独占、全权本地开发授权、不push、230 L0挂起。目标是新增私有正文表，不启Provider、不重启API、不运行业务任务。

1. 显式colima-aos-extension/aos-a0v-recovery-pg/aos_meta_head只读核查当前011、public表数与逐表行数。
2. 保留长期测试模板aos_upgrade_check_f1dc452abade为011。在本波唯一创建的一次性克隆上正式Alembic upgrade a0v_012（不是手动调用upgrade函数），明确清除当前进程AOS_DATABASE_URL干扰、仅内存构造连接配置，不输出凭据。核验唯一head、RLS、正文表空、原表行数不变，然后删除本次临时库。
3. 实际变更前独立pg_dump到仓库外0700目录/0600文件，记录路径、size、SHA256，失败不继续。明确状态仍011后正式upgrade012，比较所有原表行数、仅新增空正文表，保留备份及sanitized result。migration本身事务化，失败先查实际revision，禁止盲重放。
4. 不修改恢复磁盘/原始备份、不终止其他连接、不使用其他Docker context、不向正文表灌fixture。仅证据文档提交。API仍旧代码，后续部署组合前再核验迁移与retention启用条件。
