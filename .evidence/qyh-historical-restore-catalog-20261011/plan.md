# 历史完整恢复目录验收

Rules：AGENTS、aos-engineering-delivery、231-4、D-wave栖月汇历史实例恢复兼容清单。

候选一名称修改仍待授权；候选二恢复基线目录核验已登记且不依赖真库写入，本轮选择二。仅新增本目录与更新D-wave，产品源码不改。

固定source原cluster/aos_meta_head@092、target ccaaaa4655a86f0beba1bcbcce8891def8146abfd55b3561c5872be53791216e/networknone/无MountsPorts。比对全schema-only dump，剔除仅随机restrict令牌，任何其他差异逐行解释：仅接受已知相邻AND括号 regroup且pglast AST叶顺序一致；不是通用语义等价。

角色flags/settings/membership/grantor精确比对，不含密码。数据库owner/locale/ACL校验；source有PUBLIC Tc、ownerCTc及两transport CONNECT，target默认缺两CONNECT，允许仅在这个隔离target追加这两精确GRANT，保持source只读。记录意图与终态，禁止未知结果重发。

pg_sequences参数/Owner及每条sequence的last_value/is_called完整比对。最后578原表source和target指纹保持。本轮不执行67步迁移、不启动业务；完整来源/实际迁移/首链仍独立待验收。
