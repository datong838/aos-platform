# 历史全库恢复实际结果

原cluster7683855731447750695/aos_meta_head@a0v_092，130645015bytes。预检其他会话0，aos_app原bootstrapOID10。固定原镜像及原命名卷来源；未改现有服务或库。

pg_dump自带一致snapshot完整备份，globals不含角色密码；private目录0700/文件0600且git排除。第二份是单份dump的校验副本，bytes/SHA完全一致；不冒称第二独立snapshot。backup-manifest.json保存准确大小/hash。

隔离目标aos-qyh-history-restore-20261011，容器ccaaaa4655a86f0beba1bcbcce8891def8146abfd55b3561c5872be53791216e。独立tmpfs1G，network none、PortBindings空、Mounts空，源命名卷未挂入。没有API/Host/worker/Provider或旧Run运行。角色restore只略过匹配OID10已存在的CREATE ROLE，其余ALTER及grantor原样。

原全库pg_restore --exit-on-error成功；578张非系统ordinary table原count/排序MD5指纹与源完全一致；源前后578表完全一致。MD5/count是变化对账工具，不当密码学防篡改证明。序列、函数、角色密码及完整schema/ACL仍须下一门对账，不以表指纹替代全对象比较。

工具观察句柄后来不存在；没有据此重放脚本。独立回读result.json、source-before/after/restored及容器固定id/network/mount事实，恢复成功终态有一致证据。原脚本开头intent存在拒绝重复执行，未知效果先对账。

原不可变迁移链静态AST核对：093到159连续67步，精确文件SHA保存migration-path.json；尚未执行，不宣称迁移兼容。下一已登记门为roles/ACL/schema/sequence对账，然后分步迁移与零业务副作用证明；保持旧12Run未知外部结果不执行。

全部产品源码未改，22项既有tracked修改未覆盖。正式当前159的恢复/激活及八工作台浏览器仍未完成，Goal active。
