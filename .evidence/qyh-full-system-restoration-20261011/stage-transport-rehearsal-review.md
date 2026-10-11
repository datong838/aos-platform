# 配置登记连接：完整数据恢复与实际认证演练

本波对应完整恢复Task里的“登记连接恢复准备”，不是独立产品或另一电商租户。当前真实栖月汇库/命名卷/API/Web未更改或重启；两演练容器network none、无端口、不挂载权威命名卷，临时数据与新技术LOGIN只存在于演练容器。原当前角色、权限、旧口令、预算及历史Run保留。

实际完成全库custom dump与不含角色口令globals的第二份checksum一致备份；r2恢复全部647表，源与恢复库逐表count/hash完全一致。独立读回另外比较38个保留角色的公开属性、11个原角色membership（含grantor及admin/inherit/set）、1887个relation owner/RLS、6159项relation grants、124项column grants和461项function owner/security-definer/definition hash，全部逐项相等。这里只证明已比较的六类元数据，不声称所有PG系统目录或历史密码恢复。原历史口令未复制；本Task演练LOGIN使用私密新随机口令。

最终有效认证证据：stage-transport-r2-authentication-independent-readback.json。实际容器进程读取的HBA字节hash等于私密目标，pg_hba_file_rules显示该账户loopback SCRAM及其余reject；PGPASSFILE真实连接成功、无passfile的-w连接拒绝。原query/lookup对真实保留user:dev会员的不存在请求返回NULL。原阶段四个真实42501拒绝为直接stage表、直接configuration表、Host函数与dev-org跨租户。会员主体来自原132开发身份及保留库membership，不冒充正式OIDC、独立publisher或业务Owner。0enqueue、0business SQL写。

必须保留的失败及修正：r1 globals停在角色步骤，原grantor与新bootstrap不等价，在BEGIN/ROLLBACK真实复现42501；r2首轮停止后只读证明只有aos_app bootstrap、业务库不存在，没有持久源role/授权。初始pg_isready可能对应entrypoint临时PG，修订为PID1=postgres+ready；仅已证明零效果的globals阶段用独立续接intent继续，不重建既有资源，不重做backup、不未知重发。保留原backup/创建intent/log。

r2最初stage-transport-r2-terminal.json中的SCRAM描述过早：Docker cp退出0但实际tmpfs中的HBA仍默认trust，无密码负门成功，不能把该terminal当密码认证通过。认证独立修复intent先核同一容器状态与HBA差异，再在容器进程命名空间stdin写入HBA、核实际字节、reload并验正确密码/无密码/查询；只最后独立readback证明认证。最新可复用演练入口同时修复bootstrap同名CREATE ROLE例外、最终PID门、HBA实际字节门与无密码负门。5文件语法检查及diff检查通过；历史已存在intent使原入口拒绝重放，未为代码修订再次创建role/容器。

恢复例外依据：[PostgreSQL 16 GRANT](https://www.postgresql.org/docs/16/sql-grant.html)关于bootstrap grantor/ADMIN语义，[pg_dumpall](https://www.postgresql.org/docs/16/app-pg-dumpall.html)说明bootstrap角色已存在。r2唯一省略的语句是CREATE ROLE aos_app；原ALTER ROLE、GRANTED BY、业务owner/ACL均恢复并独立比较，不删除原grantor、owner或权限。

最后只读确认真实库HBA为/etc/qyh_pg_hba.conf，只有qyh_restored_api_login使用SCRAM、其他网络用户reject；演练tmpfs复制问题不扩散为真实库故障。没有修改源码/正常功能或原22个tracked改动；新内容均在本Task目录，private文件不提交。

当前限制和下一步：这完成了“完整恢复后可重建最小登记transport”的演练输入，尚未在真实库创建该技术账户或接到原API；当前普通运行角色的Source写权限仍使原stage消费预检失败，正式身份/独立发布/Owner/当前预算仍待。下一波先将完整Source Writer控制面/受限连接按原已批准安装协议准备和验证，保持原AIP写功能可用，才在当前库精确维护接线。不能把技术LOGIN或隔离演练当完整恢复、八工作台可用、自然首链或正式发布通过。整体Task与Goal ACTIVE。
