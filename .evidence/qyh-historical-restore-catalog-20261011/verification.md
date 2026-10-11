# 历史恢复基线验收

原库092只读，目标固定ccaaaa4655a86f0beba1bcbcce8891def8146abfd55b3561c5872be53791216e、原镜像、networknone/ports空/mounts空。

原globals角色flags/settings、成员/admin/inherit/set/grantor精确一致，角色密码排除。数据库owner/encoding/locale/ACL一致；target默认ACL缺两个source transport CONNECT，已在独立目标事务补回两条精确GRANT，记录acl-intent与catalog-after，source没有GRANT/DDL。

源与target schema-only dump归档private0600。随机restrict令牌剔除后逐行比较：15处CHECK相邻AND括号分组差异，pglast180004 AST仅移除位置/展开相邻AND且叶順序不变，其余所有行逐字一致；不能冒称raw SHA一致或一般PG16语义认证。

11条序列pg_sequences参数/Owner及逐条last_value/is_called全部一致。原578普通表count/排序MD5 fingerprint在source/target均保持；零业务执行环境保持。compare.py退出0，result.json和compare.log一致。

未修改产品代码/源库/当前API。此基线是后续67步隔离迁移的输入，不证明159迁移兼容、当前安装恢复、Host准入或自然首链。下一D-wave节点明确登记逐步迁移+数据保持+禁入核验。
