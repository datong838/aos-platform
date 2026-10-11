# 当前栖月汇完整Source边界克隆

复习231/原s3owc独立发行合同、完整恢复/Source拒权RED和累计复审。基线39f65f17b/AOS-001879，当前唯一正向org-org/dev-project，权威qyh-restored-pg-20261011/aos_meta_head@a0v_159/原命名卷与cluster固定。候选一完整克隆权限/guard演练，已登记且可安全独立；候选二正式企业OIDC/独立系统与publisher接入，缺既有来源配置，不能用开发身份代替。先一。

新Task只持有本证据目录与独立clone维护scope，排除当前卷/API变更。prepare_clone.py只读校验原container ID/image/命名卷、cluster/schema、647表、binding全关闭；当前API保持只读，Host/worker/Provider不启动。pg_dump完整custom与no-role-passwords globals，新私密0700目录、0600文件并各自第二份hash精确一致；备份前后逐表fingerprint相符。第二份是可校验副本，不伪称独立第二数据库快照。

新容器qyh-source-boundary-clone-20261011使用相同PG image、tmpfs512m、仅127.0.0.1:18431，无权威卷挂载，无应用/worker。未占用端口/不存在容器才能建立一次intent；任何未知结果先对账，不重发。bootstrap使用原aos_app以保留grantor，仅跳过globals中已存在的CREATE ROLE aos_app这一行，其余角色属性/成员/ACL均完整恢复；不复制原登录密码、不宣称SCRAM凭据恢复。

新库aos_meta_head全pg_restore --exit-on-error，不--no-owner/--no-acl，不过滤失败对象。恢复后独立核对所有647表和全部39原角色/成员、relation RLS/owner/grants/column grants/functions；克隆cluster必须与Source不同，Source原数据/metadata再次相符。没有完整相等不得进入后续ACL/guard演练。

本步只有完整克隆基础判据，不能宣称Source迁移、发行连接/全部写者权限闭合或八工作台恢复。克隆资源与私密备份保留，不删原卷/备份、不push。后续所有Source写权限/operation guard测试仅在该clone零执行环境，兼容全链后再独立正式当前库迁移门。

完整恢复相等后，追加一次原API LOGIN→SET LOCAL ROLE aos_runtime的Source反证，绑定clone精确cluster/端口，不复制当前密码。使用原事务租户绑定，INSERT随机Plan head与Plan操作Receipt；只在隔离clone的未提交事务执行，finally rollback并独立全647表hash核对。若原API登录默认只读，仅在clone连接上显式开启事务读写，测试数据库权限是否独立阻止伪造，不把客户端默认只读当Source ACL安全边界。记录accepted/rejected和SQLSTATE，不预造PASS；未提交事务不是业务执行，当前库无连接/写操作。
