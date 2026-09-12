# 专用登记连接与启动组装验证

2026-09-13，基线0f906007。新增 ecommerce_growth_registration_connection.py；main lifespan 将明确配置的连接选择结果交给控制平面，默认None。仅支持 AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE 指向固定schemaVersion/role/dsn文件，不接收浏览器连接信息、不回退Web/runtime身份、不通过环境传递DSN。

文件要求绝对路径、当前UID普通文件0600、最多64KiB，NOFOLLOW/NONBLOCK，拒绝符号链接、管道、重复字段、错误结构和未知字段。连接或文件错误只给固定信息。连接前读取文件，连接后独立短事务核验登录名称、非super/bypass/createrole/createdb/replication、NOINHERIT；可达角色严格等于runtime+maintainer，两组角色无登录及高权属性，不得额外继承或拥有admin_option。核验结束IDLE后才交Owner。

RED：模块缺失时测试收集失败。GREEN：专用连接、启动、Owner PG、HTTP与控制平面五组87 passed（19.21s），18项既有模型/OpenAPI警告。实际18432隔离PG：合法非特权双角色连接通过且交付IDLE；superuser、声明名不符、缺runtime、额外pg_read_all_data、admin_option和INHERIT均拒绝，未交付连接。坏权限/属主/相对路径/符号链接/管道/重复字段/超大/损坏/缺失文件不连接；连接异常不回显哨兵内容。启动仅组装且生命周期退出清理服务，未调用连接。

AR2 ar2-7：1817扫描/158分类/93迁移，五类错误为空；diff检查通过。无主库身份创建、权限GRANT、026/027迁移、登记请求或API重启。

限制：此检查限定登录与角色图，不等于所有表/函数ACL已收敛；已有主库runtime宽写权限差异仍待评审。隔离PG使用受控fixture，不代表真实经营链完成。接下来的完整登记验证需结合真实当前四来源、签名、明确受限身份与HTTP，仍要补首次fenced切换及未激活撤销/卸载，才进入自然源事件业务首链。

下一波：形成主库/迁移权限差异与最小收敛方案，补隔离完整依赖端到端登记，并评审首次fenced切换/撤销路径。保持m1单写、不push、230 L0挂起。
