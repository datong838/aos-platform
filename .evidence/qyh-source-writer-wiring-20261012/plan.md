# 原Source专用连接的生产接线

依原s3o-w-h/k/n、Source-writer-impact-r2及当前18原生PASS基准，原Store早已有可注入的同调用方事务factory，连接支持3固定purpose/身份/私密passfile/精确DB/scope重绑；当前router未使用，是下一已登记代码缺口。仅接配置与factory，不重写Source业务校验、SQL发行协议或原事务边界。

精确文件：
- /Users/ddt/work/projects/ai_agent/aos-platform/services/aos-api/aos_api/aip_source_issuer_wiring.py（新增）
- /Users/ddt/work/projects/ai_agent/aos-platform/services/aos-api/aos_api/routers/aip_production_contracts.py
- /Users/ddt/work/projects/ai_agent/aos-platform/services/aos-api/aos_api/routers/aip_content_drafts.py
- /Users/ddt/work/projects/ai_agent/aos-platform/services/aos-api/aos_api/routers/aip_responsibility_assignment.py
- /Users/ddt/work/projects/ai_agent/aos-platform/services/aos-api/tests/aip/test_aip_source_issuer_wiring.py（新增）

接口 configured_source_issuer_factory(purpose)：purpose固定plan/content/contract，各自AOS_PLAN_SOURCE_ISSUER_CONFIG/AOS_CONTENT_SOURCE_ISSUER_CONFIG/AOS_CONTRACT_SOURCE_ISSUER_CONFIG。未设置返回None，沿原constructor回落，保留已有正常功能。设置后只允许用户自有0700目录/0600普通非symlink JSON文件，限16KiB、重复key拒绝、严格schemaVersion=aos.source-issuer-database/v1与精确purpose/host/port/database/passfile六字段，不接受DSN/密码/可变role等额外字段。读取位置固定在factory创建时，实际调用时重新核私密配置与原BIIssuerDatabaseConfig/passfile；显式错误不得回落普通runtime。

host/port/database必须与当前db.get_dsn()规范化的实际目标三元组完全相同；只取三元组，不打印DSN/口令。复用原connect_source_issuer_write，不自造connection/SET ROLE/COMMIT/CAS/借Owner或扩大roles。原Scope按原对象传给连接；凭据和环境不进入日志。配置只是技术连接，不授Source caller/Root/Owner/预算/安装审批或执行权限。

生产Contract router注入plan与contract factory；Successor router只注入plan_connect_factory，非Source takeover保留原connect；Content router原Store只有register写事务，注入content connect_factory，原Content verifier/readiness不变。原BI IPC与独立进程路径保持。默认Source未配置、真实库ROLE/ACL不动、Host/worker/Provider继续关闭。

RED与验证：无配置默认与unknownpurpose；三purpose正确精确调用与Scope保持；wrongDB/port/host、purpose错配、非法文件权限/symlink、重复或额外字段、显式无效配置均在连接前拒绝。相邻原connection/BI/三个route的鉴权/正常事务与native Scope/role checks，旧fallback正常保留。新增安全逻辑做有意义测试，不用单纯AST计数当真实接线。标准测试原生复验只隔离UUID库/角色，不碰真实库。交付后必须精确冻结最新m1 API源码再安排受控预览重载，旧候选和22用户修改不覆盖。整个Source生产全37操作、权限部署/克隆切换及八页仍未完成，不因factory/helper通过宣称全恢复。

专项补充：真实命名管道作为配置会在普通open前阻塞，已用独立子进程2秒超时得到RED；添加O_NONBLOCK并仍以fstat拒绝非普通文件，避免坏配置阻塞API。原Role/业务规则不变。首次专项忘记显式测试DSN导致默认5433连接失败，未进入任何测试/数据写，不计GREEN；相邻首次从仓库根启动使旧测试相对alembic路径不存在，58PASS1路径失败，改为原API工作目录后整体复验，不修改旧测试或迁移。所有日志保留。
