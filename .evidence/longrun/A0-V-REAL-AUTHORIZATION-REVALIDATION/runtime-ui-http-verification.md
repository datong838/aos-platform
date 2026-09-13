# UQ4-B HTTP与专用API连接验证

基线c5a4bfe2，m1单人串行、不push、230 L0挂起。新增ui_read_connection.py、ui_read_http_service.py，现有runtime_workshop路由增加POST /reads与GET /reads/{request_id}。lazy目录增加resolve_catalog，旧GET目录保持接口不变。

只读取AOS_RUNTIME_UI_READ_CREDENTIAL_FILE的绝对路径0600本用户普通文件；严格三字段schemaVersion/role/dsn，无软链接/FIFO/重复字段或Web/runtime fallback。真实LOGIN必须NOINHERIT、非超级/非bypass/无管理权限，唯一可达aos_ui_read_api，不允许ADMIN或该角色继承别的角色。事务固定READ COMMITTED、同scope/subject和专用SET ROLE，成功提交异常回滚。没有实际创建主库身份或安装配置。

提交只收固定经营参谋读取与Idempotency-Key，202；查询200；当前Principal唯一提供scope/subject/markings。错误脱敏；读取路由正常、验证失败、身份及业务拒绝均no-store。请求验证保持项目400约定，不回显输入。未配置连接503，匿名401/403，不伪造空成功。

验证：48 passed、7已有warnings，包括15文件/真实身份事务、11HTTP、8旧目录及14查询/服务组合。scope覆盖、任意operation/SQL/超限/缺键/匿名在服务前拒绝；成功查询可重读且队列和Attempt不重复；真实专用身份成功提交和异常回滚已验证。安装签名目录/baseline及OCI仍使用此前已说明替身，尚非真实业务验收。

AR2扫描1849模块/163分类/93迁移，错误数组全空；git diff --check通过。主库仍030、旧API/原宿主未重启、新凭据未置备、真实UI未交付。

下一波UQ4-C：严格Web提交/查询客户端、有界等待、未知结果不自动重发、scope/subject/签名target变化立即丢弃。UQ5后继签名包原方法和页面挂载，UQ6真实升级与首读，UQ7经营闭环八场景。
