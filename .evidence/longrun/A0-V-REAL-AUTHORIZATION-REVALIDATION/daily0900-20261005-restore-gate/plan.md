# 最新m1每日重启：135→142独立完整恢复演练门

Authority1329/HEAD6b76d4d3，唯一m1写者，Task w5cb4-daily0900-full-restore142-gate-20261005已登记。复习231-4、栖月汇原权威归属与七迁移：136新Source/proof表，137撤销中性fence，138原build provenance，139初始化协调，140冻结Source原metadata，141独立批准ACL，142独立发行ACL/原三记录约束。全部不供给正式LOGIN、旧来源许可或业务启动权。此Task仅准备/演练，不执行当前135迁移，不停止/重启原服务；正式迁移与最新启动为下一独立门。

## 文件与确定性执行路径

新增scripts/a0v_current_142_restore_gate.py、scripts/tests/test_a0v_current_142_restore_gate.py。先合同RED，再最小完整执行器；不复用硬编码旧118/135来源的旧脚本，保留其控制原则。新私有状态目录由执行器创建在aos-recovery，父/目录700、所有备份/日志/JSON600、O_EXCL不覆写；不把秘密或数据行输出共享证据。源参数仅原bootstrap私有读取，密码不进命令参数/环境/日志/Receipt。

原权威容器/命名卷/端口/库135与m1 HEAD、唯一代码142严格核对；原库REPEATABLE READ READ ONLY事务导出snapshot。全部public原表逐行SHA256排序摘要及行数、原序列last_value/is_called、原角色有效表ACL与RLS策略采集，仅摘要出共享证据；row原文不出私有内存。快照内docker pg_dump -Fc --snapshot生成新当日独立全备；pg_dumpall --globals-only --no-role-passwords保留角色恢复信息，记录文件SHA/大小与原pg_restore --list成功/TOC。

目标在colima-aos-a0v-test-only新建nonce容器/卷，复用本地已有同PG major镜像（--pull never），--network none/无端口、仅新命名卷，不带源卷/宿主bind；本地socket test-only trust无生产密码，独立新管理员与源角色不重名。restore-intent先持久，存在intent/输出拒绝二次执行，未知只读对账。新globals完整恢复源角色属性/成员和无密码角色定义，然后模板0新clone库与完整pg_restore --exit-on-error --single-transaction，不使用no-owner/no-acl。

恢复后全部原表SHA/计数、序列、原角色有效ACL、RLS必须精确一致。七迁移用原Alembic离线编译精确step的BEGIN/COMMIT SQL，通过目标本地psql ON_ERROR_STOP逐步事务执行并每步实际回读版本；不能手写替代DDL，不能修改guard。所有源表原行须不变（alembic_version除外；两个metadata表仅允许预定的两个ID新增，所有旧行SHA集合保留）。源序列与原角色旧表有效ACL/RLS保留；新增三role默认NOLOGIN/无高权/无成员，新Source/proof/provenance/fence无业务回填，原binding/runtime绑定/Host及canary保持原值。

演练后再只读源135并复核原快照摘要无漂移；最新签名Receipt/tree保持原预检结果的签名通过而版本漂移仍独立标记，不把clone142当当前142，也不改启动器guard。新目标容器/卷/clone/备份全部保留，不DROP OWNED/删库/卷或覆盖旧资料，不自动重试未知输出。

## 验证与恢复

首次run-r1 terminal exit2：新一致全备4228767bytes/SHA cffc35fbe7611738e1f629c08f3ed187f88bdb1cc75679b67879f869f28c3b1c/TOC5905；新隔离aos-daily142-f8c8c1b6bae3保留。原globals角色定义已创建，第一条GRANTED BY aos_app因原bootstrap grantor缺ADMIN身份拒绝；以aos_app同名但非bootstrap新角色重试单条事务也拒绝，ROLLBACK，无正式grant。不是源库异常，不自动重跑未知步骤。

修订独立恢复实现：源当前pg_roles oid10实际aos_app；新network-none容器bootstrap改为同名aos_app（只本地trust、无生产密码或正式授权）。新globals输入仅去掉恰好一次的CREATE ROLE aos_app;，保留原ALTER ROLE及全部原GRANTED BY成员关系；原备份/globals文件不改，另存派生SQL与SHA。源/目标bootstrap名必须实际核验，重复或缺失CREATE/非aos_app源bootstrap拒绝。所有原role属性、成员/选项及grantor一起比较。第一次目标/卷与备份完整保留，已确认terminal并按新执行器进行新的独立nonce目标/新一致备份；不删除/修补原目标。此修订替代“新管理员不与源重名”的错误恢复设计，不能靠降低原成员关系或改grantor取得通过。

第二次run-r2 terminal exit0，9.503s：592原表/五新空表、Source两metadata增量、旧有效表ACL/RLS/函数/序列/角色成员及grantor核对成立，源135未变。扩大权限审查发现未覆盖数据库级ACL：源PUBLIC只有TEMP、无CONNECT，而异名CREATE DATABASE+pg_restore默认PUBLIC有CONNECT，23非owner角色有效CONNECT漂移；单次原始GREEN因此仅上述窄范围，不可作完整门放行。证据保留不改旧日志。

修订：新nonce network-none独立集群中使用原数据库名aos_current_preview_20260927，保留独立目标context/container/volume身份，绝不使用当前18435连接执行DDL；pg_restore --create --exit-on-error -d postgres恢复原库自身ACL/属性/设置，禁止异名预建库丢DATABASE ACL。CREATE DATABASE不能位于single-transaction，故独立目标完整恢复按原archive多事务、失败保留不覆盖；七迁移仍每步事务。新增snapshot项：24原角色数据库CONNECT/CREATE/TEMP、public schema CREATE/USAGE、role config hash、数据库编码/locale/connlimit/owner/ACL、数据库及role-in-database设置hash；恢复和迁移后均精确一致。权限先RED（CONNECT从false变true必须拒）再修实现。第三次独立完整门成功前不迁移源，不以同名数据库或test-only trust冒充当前库/正式登录。

合同测试覆盖有源卷/host bind/端口/网络/非隔离名/已有状态拒绝、原表丢失或原hash变化拒绝、metadata非法额外添加拒绝；实际完整恢复演练证明主路径，测试mock仅合同不能作恢复GREEN。失败保留intent/完整私有stderr、源135/旧服务不动；只读排障后先补方案，不delete/recreate同目标。执行节点记录真实耗时。无UI变更，本门浏览器不适用；完成Evidence/Delivery/精确提交与AOS/Prime上下文后立即下一独立停机一致备份/恢复/正式迁移门，再PG→API→Web及真实浏览器验收，b90完整evaluator继续。

r3 terminal exit2 exact_restore_compare：原库自身恢复及24role有效数据库/schema权限已一致，唯一差异为datacl原始数组条目顺序（PUBLIC/owner互换）。不忽略ACL，改为aclexplode规范化完整grantor/grantee/privilege_type/is_grantable排序JSON；保留数据库属性精确一致。新测试确保顺序不同不改变规范化权限，实际r4再独立新目标验证；r3所有资料保留。
