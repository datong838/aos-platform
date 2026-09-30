# BG00ES 私有配置与只读启动预检

基线AOS-001007/m1@725210d5，复习BG00ER进程配置、BG00EM数据库身份和函数门。新增`services/aos-api/aos_api/aip_network_consumer_config.py`及`services/aos-api/tests/aip/test_network_consumer_config.py`。

配置载体是显式绝对路径私有JSON：父目录0700、文件0600、当前euid所有、非symlink/常规文件、限16KiB。parent/file分别O_NOFOLLOW+dir_fd打开，fstat后读取；拒绝重复键/非标准常量/extra字段/不准确类型。schemaVersion1、socketPath、apiUid、consumerUid、ipcGid、database{host,port,database,passfile}、attemptDirectory、maxConnections、acceptTimeout。不允许密码/token/DSN/role/SQL，错误脱敏，文件只保存passfile路径，绝不读取其内容。复用ConsumerDatabaseConfig和ConsumerProcessConfig，不再复制校验逻辑。

只读preflight接受显式TenantScope，验证当前OS UID/GID与外部OIDC配置、私有attempt目录、socket0750目录/占用状态，然后只读连接指定DB，复用现有精确数据库身份及120/121/122函数属性/ACL门。显式scope只用于只读连接上下文，不是业务授权；每次请求仍原JWT/tenant/actor/approval门。预检不创建listener、attempt或业务数据，返回有限布尔状态，不输出路径/凭据。

先RED真实私有文件/字段/权限/重复JSON；真实隔离PG预检正向和无写入、错误scope类型/当前OS身份拒绝。当前正式进程/ACL/IdP/部署仍未达，不能用测试配置替代。m1单写、不push、真实118库只读、不读商城源/旧Run、不手工run_definition，230 L0挂起。
