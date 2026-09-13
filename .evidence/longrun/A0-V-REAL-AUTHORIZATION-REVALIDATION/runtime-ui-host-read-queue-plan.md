# N8 UI → 原宿主签名读取投递技术方案

基线41ed8fc8。此方案补充原AR2 N7/N8、runtime-workshop-routed-ui-plan，不另起业务主线。已确认API18181与运行宿主PID6606分进程；LivePreparedJobDirectory为进程内真实实例目录，CurrentInstalledPackageInvoker只能在持有PreparedJob的原宿主调用。现有PostgresRuntimeAttemptStore支持signed_read、owner token、期限、immutable事件和排空恢复，必须复用。

## 目标与边界

只开放固定只读操作 analyst_workspace_view_v1。Web发起请求只提交当前RuntimeUiInvocationTarget、moduleId=ecommerce.analyst、caseLimit/runLimit；不接受SQL、URL、包路径、任意operation或原始业务payload。服务端绑定当前subject与TenantScope。队列不是执行授权，不改变九项业务命令dispatch/cutover，不创建第二个包实例。

宿主原有租户assignment串行领取本租户任务；请求目标必须命中自身LivePreparedJob。Claim前/完成前均核当前安装、signed UI声明与module权限、当前成员与markings。原canonical snapshot reader在repeatable read/serializable事务形成快照，包投影仅消费该快照。IPC在事务外，通过CurrentInstalledPackageInvoker进入原实例；读取执行进入既有signed_read Attempt及排空协议。

## 数据与状态

新增extension_runtime_ui_read_request，租户复合主键request_id、唯一(subject,idempotency_key)、request_hash及不可变target/limits/subject/deadline。接受时仅requested；claimed绑定一次owner_token_hash、attempt_id与snapshot_hash。成功写result_hash和有限result_json并进入succeeded；拒绝/失败/期限到进入denied/failed/expired。终态不可变，不重置requested；同键不同hash冲突，同键终态仅回读。命令体与provider数据不能经该表进入宿主。

已有extension_runtime_execution_attempt仍是实际调用/排空权威。请求行仅投递状态，不凭state=succeeded授业务执行许可；实际worker须先完成Attempt再封存同一结果。崩溃后已领取或结果不明任务终结为failed/expired，不重放；用户以后新读取使用新请求键、重新读当前事实。取消浏览器等待不取消原运行宿主或其它请求。

DB隔离沿用现有org_id/project_id GUC+FORCE RLS。API不能更新claim/结果或直接写Attempt，宿主不能代替主体凭队列标记执行；使用固定SECURITY DEFINER接入函数/明确角色，限定search_path并撤销PUBLIC，禁止向Web角色授予成员表UPDATE。当前诊断profile不是生产身份达标证据。

## 分片及退出条件（自动衔接）

1. UQ1：严格请求/结果合同与a0v_031加法迁移，fixed read kind、状态/immutable/RLS/权限；真实隔离PG通过负租户与无越权修改测试，主库暂不迁移。
2. UQ2：当前主体/签名门禁下入队与同键回读、限流和期限、exact target；拒绝不写入，未知不重发。
3. UQ3：既有宿主assignment中的具体只读消费者，复用Attempt、源快照与原PreparedJob；双worker/失效代次/中途撤权/关闭排空测试。
4. UQ4：独立API提交/查询及Web等待结果，旧资源失效即撤下，命令入口继续关闭；不暴露原始异常或跨租户结果。
5. UQ5：后继growth包加入纯投影invoke分支及签名前端资源，operations-base另包保持7+1；OCI及资源交付逐hash验证，旧包不可覆盖。
6. UQ6：备份与规范主库迁移、原宿主升级/恢复、新包安装配置，通过真实页面及隔离租户读取；新审批主体仍必须是现实独立身份，不自签评审。
7. UQ7：回到真实首链与八场景，源更新/Case/Run/分析/exact评审/内容任务/受控能力/产物/续跑/复盘Wiki逐证据验收，再连续观察和发布决定。

## 文件计划

UQ1修改services/aos-api/alembic/versions/a0v_031_runtime_ui_read_request.py，新增extension_runtime/ui_read_contracts.py与tests/extension_runtime对应合同/PG测试。其后文件在每个分片开工前细化，所有结果补入closure-manifest与项目两份接续文档。任何单元GREEN都不把UQ6/UQ7标完成。

## UQ2-A 入队存储切片（基线6ca66615，编码前补充）

新增 extension_runtime/ui_read_store.py 与 tests/extension_runtime/test_ui_read_store_pg.py；复用当前成员事实与canonical_sha256。仅内部事务端口，暂不授予API写入权限或暴露接口。签名模块和当前UI门禁由UQ2-B具体接入服务完成，在此之前不能宣布UQ2完成。

方法要求现有 READ COMMITTED 事务与同租户GUC，当前成员读锁；按租户 advisory transaction lock 串行所有入队，先核同主体同键记录：同摘要原样返回、不同摘要拒绝。新请求限制同租户未过期requested/claimed最多64条、同主体最多8条；期限固定数据库时间后60秒，UUID由服务端生成。过期请求不自动重放也不改历史。所有拒绝在INSERT前发生，数据库trigger再次核当前绑定版本。该端口不执行包、无成员修改、无自建事务commit。

验证使用隔离真实PG，核同键回读、冲突、主体隔离、成员撤销、并发额度、调用者回滚。规范请求摘要须与UQ1数据库算法一致。未集成签名门禁前不增加角色INSERT/函数EXECUTE授权。

## UQ2-B 当前签名资源接入（基线e4da3721，编码前补充）

新增 extension_runtime/ui_read_admission.py 和对应测试。具体服务依赖既有 RuntimeWorkshopCatalog；不得接收Web提供的目录条目/权限标志。调用者事务内锁住当前成员及所需markings，使用这些当前事实重新加载已验hash的目录。只接受唯一ecommerce.analyst模块、完全相同的七字段target、固定readOperationClaim；目录角色/markings再明确比对，才进入UQ2-A存储。相同键回读同样先重新校验资源和当前权限。目录自身读取使用独立只读快照；最后INSERT的binding guard核epoch/revision，宿主领取仍必须重新做全部门禁，因此入队不是执行授权。暂不新增HTTP或数据库写角色授权。

退出：门禁拒绝时存储调用为零，旧资源/撤权/command-only声明/错模块/错scope/重复模块均拒绝，合法固定读取交给原存储。该切片完成仍需受限数据库接点及UQ3消费者后才能真实调用。

## UQ2-C 专用数据库接点（基线e0d84563，编码前补充）

新增a0v_032_runtime_ui_read_admission.py。角色aos_ui_read_api为NOLOGIN/NOSUPERUSER/NOBYPASSRLS，仅固定函数EXECUTE；不授予成员表UPDATE、队列表DML、Attempt权限。固定SECURITY DEFINER函数限定search_path、显式租户条件，要求实际session_user为非超级/非bypass且属于该角色、SET ROLE正确、READ COMMITTED。subject必须匹配aos.subject GUC。函数一锁定当前membership及指定bearer markings，函数二只接收严格固定请求并调用函数一，按租户锁、同键摘要、8/64额度入队，返回无业务result的投递摘要。公开函数均撤销PUBLIC。

隔离PG用真实非超级LOGIN身份+SET ROLE验证；错误GUC/subject/角色/直接DML/Attempt访问均拒绝，正常请求摘要与UQ1一致。应用接入下一切片切换到这些固定函数；当前UQ2-A/B存储代码不因迁移自动获得权限。主库部署待UQ6。数据库入队仍不是signed UI授权，宿主必须重新校验；HTTP接入服务必须先运行UQ2-B。

## UQ2-D 应用使用受限入口（基线4952795e，编码前补充）

新增extension_runtime/ui_read_api_database.py，修改ui_read_admission.py。应用当前主体读取/入队均调用public限定的a0v_032函数，先核调用者事务及TenantScope GUC，拒绝remote OpenFGA的本地降级；校验返回摘要等于本次规范请求、终态枚举/UUID/期限类型，返回固定投递合同。既有ui_read_store暂保留内部端口与其并发测试，不对API授予直接表权限。

接入PG测试改为aos_ui_read_api非超级LOGIN，通过测试专用schema连接转发仅重定位public函数名，实际事务/行锁/权限均由PG执行。目录输出替身仍只验证门禁顺序，真实签名目录验证沿用独立测试。合法读取贯穿当前身份→签名声明门禁→固定函数；拒绝无新行。同键旧资源或撤权仍拒绝。下一步UQ3原宿主消费者，不凭队列接受触发任意操作。

## UQ3-A 单次领取与封存存储（基线a8707a06，编码前补充）

新增extension_runtime/ui_read_worker_store.py与PG测试。只处理调用者事务内指定request_id；请求行FOR UPDATE锁使双消费者至多一个取得claim。核固定合同摘要、未过期、精确当前binding后创建既有signed_read Attempt（operation_key=ui-read:requestUUID），随机owner token仅留内存且不出现在repr。snapshot_hash进入Attempt请求摘要；队列claim和Attempt同事务提交。已领取/终态请求不重新返回执行claim。

封存精确claim、版本、token、Attempt；先settle Attempt再更新队列，同一事务原子提交。成功前再核binding；过期或失效转失败/expired，无自动重发。未知结果由后续恢复器收束，不创建第二次Attempt。代码不调用包、不读取业务表、不授予新角色权限；具体宿主消费者仍负责当前成员、签名声明、快照及同一PreparedJob校验。

固定UI读取operationId直接保留analyst_workspace_view_v1，后继包注册独立只读方法；不能把读取塞进analysis_advance等九项业务命令。新包交付前只做隔离验证。UQ3后续补具体消费者及角色/关闭/恢复接入。

## UQ3-B 过期投递收束（基线20231663，编码前补充）

新增extension_runtime/ui_read_recovery.py及PG测试。原Host先执行既有ExpiredSignedReadAttemptRecovery；新存储函数每次最多100条，显式scope、FOR UPDATE SKIP LOCKED选取到期requested，或其Attempt已succeeded/failed/abandoned的到期claimed。仍running的Attempt不标成可重试或强制成功。封存expired/READ_DEADLINE_EXPIRED保留原claim，revision+1，无结果、无新Attempt、无重新入队；终态再次运行不改变。筛选跳过running而非让它占满整页阻塞其它过期请求。

隔离PG验证到期前不变、requested到期终结、claimed在Attempt仍running时不终结、既有abandon恢复后队列终结、幂等、负租户和分页。该函数仍为宿主内部存储切片，无新授权或真实调用，随后在具体消费者/Host串接。

## UQ3-C 运行角色的受限当前身份与队列更新（基线d35035a2，编码前补充）

新增a0v_033_runtime_ui_read_worker.py。宿主独立principal函数保持当前subject/scope/非超级session/SET ROLE验证，角色仅aos_runtime、隔离级别仅REPEATABLE READ或SERIALIZABLE。与API函数分离，不扩大API入口权限。函数锁成员和bearer但不授成员表UPDATE。

aos_runtime仅获请求状态、版本、claim/结果相关列UPDATE；不可插入/删除、改subject/target/deadline。既有trigger继续约束状态图与Attempt关联。真实非超级runtime账号测试读取当前事实、领取/封存，以及身份/target/deadline/DELETE禁止；API角色不能调用宿主函数。主库暂不部署。随后snapshot source使用宿主函数，具体消费者落实完整门禁。

## UQ3-D 宿主快照受限身份接入（基线9aaaef66，编码前补充）

修改ui_read_api_database.py抽取仅两个固定函数名的内部principal调用，API包装保持032，新增host包装仅033。analyst_workspace_snapshot.py机械提取现有范围/隔离预检和查询组装，保留旧入口，新增read_host_analyst_workspace_snapshot调用宿主principal包装后复用相同SQL/组装。无可注入查询或跳过权限的参数。

新增非超级host PG快照测试：角色只有canonical表SELECT和受限principal函数，无成员UPDATE；真实canonical Case/Run/State输入包纯投影有效，第二连接新Case在同一事务不可见、下事务可见。API角色不能使用宿主入口，未知主体拒绝。旧入口原测试保留，避免影响已有诊断行为。

## UQ3-E 共享读取门禁与精确实例（基线772200b0，编码前补充）

从ui_read_admission机械抽取require_current_catalog_read，用于API及宿主准备/完成前一致校验，返回签名资源条目而非执行许可。CurrentInstalledPackageInvoker新增可选expected_job，构造时必须是当前目录同租户/安装/代次的真实PreparedJob；IPC前后核同一对象。既有调用不传参数保持原行为。新增调用前被替换零invoke、调用中被替换不返回结果、合法实例成功的测试。后续具体消费者必须传领取时选中的job。

## UQ3-F 具体宿主消费者（基线c630ece6，编码前补充）

新增extension_runtime/ui_read_consumer.py与测试，LivePreparedJobDirectory新增仅同scope的实例快照枚举。消费者固定scope、PostgresInstallationStore、RuntimeWorkshopCatalog、同LivePreparedJobDirectory和可信markings；独立idle连接→REPEATABLE READ→绑定scope/运行角色→核7张请求/Attempt/binding/canonical表FORCE RLS。不使用API连接或任意SQL回调。

prepare_once先收束已终态Attempt的过期队列，仅查本进程持有的精确安装/代次请求，最多25条。锁候选，嵌套事务内当前主体/签名门禁→canonical快照→当前安装包hash比对→claim+Attempt；拒绝回滚局部准备后固定denied/expired，不保留半个Attempt。包固定solution.ecommerce.growth、方法analyst_workspace_view_v1，独立于九命令。

invoke_prepared只调用绑定expected_job的原invoker，IPC在事务外；快照摘要不可变。finish_prepared在新事务重查当前主体/签名资源，核结果固定schema/tenant/cutoff/count/无执行授权后原子封存；异常/未知不重发。Host下一切片在prepare/invoke/finish边界检查assignment身份并负责关闭等待，消费者不自行创建后台轮询或包实例。

测试将真实数据库边界与生命周期编排分开记录：已有非超级PG验证复用；新增编排测试证明事务外一次调用、撤权后不交付、结果错scope/快照或实例变更拒绝。实际OCI只读方法仍待UQ5后继签名交付。

UQ3-F复核补充：仅DB单次claim不足以防止同一Prepared对象被重复调用。消费者维护带线程锁的本进程签发登记，prepare事务提交后登记，invoke原子消费一次，finish要求已消费并在成功提交后移除；旧对象/其他消费者对象/重复invoke全部拒绝，结果不明也不释放重试机会。

## UQ3-G 原RuntimeHost调度（基线e321f1c1，编码前补充）

修改runtime_host.py允许具体RuntimeUiReadConsumer，要求consumer.scope与assignment一致，同类仅一个，排序configure→disable→ui-read。prepare在线程内提交后检查同一assignment；invoke事务外等待完成后再次检查；仅仍当前者finish。撤销时仅丢弃本进程签发对象，不重写claim或创建新调用，现有Attempt/过期恢复保留未知事实。新增consumer.discard_prepared只清理签发登记。

Host.stop保持原先等待current tick然后停止生命周期的顺序，无独立UI轮询或新宿主。真实非超级PG消费者配原Host验证正常调度、prepare后撤销零调用、invoke后撤销无结果、stop等待调用/封存。旧Host测试回归保证configure/disable/恢复顺序不变。生产依赖显式装配与主库升级仍属后继切片。

## UQ3-H 生产装配与预检（基线0f3855e2，编码前补充）

修改production_runtime.py与asset_registry/control_wiring.py，新增ui_read_preflight.py。RuntimeWorkerDependencies可选具体RuntimeWorkshopCatalog，必须共享preparation.loader，消费者复用相同store/live_directory/runtime connector；markings必须显式规范tuple。AOS_EXTENSION_RUNTIME_UI_READ_ENABLED=1才构造，markings来源严格JSON列表AOS_EXTENSION_UI_READ_MARKINGS_JSON，默认关闭保留旧配置。

启动前只读检查7张所需表存在/FORCE RLS/非当前主体所有、033函数是SECURITY DEFINER且runtime有EXECUTE而UI角色无EXECUTE、队列表runtime SELECT及11个状态/结果列UPDATE、无INSERT/DELETE/subject/target/deadline修改权。缺失或权限扩大返回UI_READ_PREFLIGHT_FAILED，不构造读取消费者。依赖中相同loader/实例目录是进程对象绑定，无新实例或后台轮询。

测试原生产selector回归、显式UI装配、错误共享loader/配置/预检失败，独立完整迁移数据库的真实非超级角色预检。主库和原服务暂不改变，真实升级仍UQ6。

UQ3-H完整库验证发现：228ti2e6_module_rls.py为public未来表设置aos_runtime默认SELECT/INSERT/UPDATE/DELETE。031/033仅追加GRANT不能移除继承的宽ACL，临时schema测试没有该public默认权限。修正为新增a0v_034_runtime_ui_read_acl.py，仅对新请求表撤销PUBLIC/runtime/UI/maintainer表级与列级旧ACL，然后精确授runtime SELECT及11个状态列UPDATE。全局默认权限和其他表不改。该发现不以放宽预检解决；完整head数据库正负ACL验证必须通过。

## UQ3-I 当前安装数据范围门禁（基线9b6aef11，编码前补充）

修改ecommerce_runtime_workshop_catalog.py，在已核验当前安装/锁和签名模块后，将模块permissions.data_scopes与当前CompositionLock permission_diff.target.data_scopes比较；未授权模块不投影。API入队和宿主prepare/finish已有fresh catalog调用共同继承该门禁，避免另造权限DTO或二次目录查询。

修改extension_runtime/installed_package_invoker.py增加默认空tuple的required_data_scopes；非空时要求当前baseline锁内授权包含全部范围，IPC前后均复核，保持旧调用和snapshot形状。修改ui_read_consumer.py，从签名entry绑定范围，将安装/包hash/范围检查前移到canonical快照读取之前。当前权限不够不得读源、建Attempt或调用包；调用后撤权不交付且不重试。

验证当前锁有/无范围的目录可见性；invoker缺权零调用、完整授权成功、中途撤权无结果；真实PG消费者缺权无快照/无Attempt/零IPC。目录与baseline替身测试明确其证据边界，主库真实授权和OCI运行仍待UQ6，不凭测试修改现实授权。

## UQ4-A 原请求人受限查询（基线1ab80639，编码前补充）

新增a0v_035_runtime_ui_read_query.py，两项固定SECURITY DEFINER函数只授aos_ui_read_api EXECUTE。metadata函数先调用032当前主体函数，再按精确scope/subject/request UUID返回固定请求合同，不含业务结果；result函数重复主体校验、精确requestHash与当前binding有效性，只返回固定状态及成功结果/摘要，失败不泄露原始异常。API无队列表SELECT或DML。

新增extension_runtime/ui_read_query.py：当前主体/markings→metadata请求摘要复核→当前签名目录和exact target/dataScopes→受限result函数→结果hash与固定合同复核。拒绝不调用结果函数；同租户他人、负租户、已撤销成员、旧资源和旧绑定不能读取。请求不存在统一LookupError，不暴露是否归属他人。该波先实现数据库及应用查询，HTTP连接身份装配和Web属UQ4-B/C。无写入、重发、新Attempt。

新增tests/extension_runtime/test_ui_read_query_pg.py，复用真实非超级API角色和宿主成功封存；校验未完成/成功/错误绑定、撤权、他人/负租户、直接表SELECT拒绝。完整迁移库回归保障新增函数不改变既有ACL。主库部署仍UQ6。

## UQ4-B HTTP与独立API事务（基线c5a4bfe2，编码前补充）

新增extension_runtime/ui_read_connection.py：仅AOS_RUNTIME_UI_READ_CREDENTIAL_FILE绝对0600本用户普通文件，严格schemaVersion/role/dsn、无软链接/FIFO/重复字段；不回退Web/runtime身份。连接后校验真实NOINHERIT非超级LOGIN、唯一可达aos_ui_read_api且不可ADMIN；固定READ COMMITTED事务SET LOCAL role/scope/subject，成功提交、异常回滚。新身份实际置备待UQ6。

新增extension_runtime/ui_read_http_service.py将同一受限事务与既有admission/query组合；当前签名catalog由现有lazy reader resolve_catalog提供。修改routers/runtime_workshop.py增加POST /reads（固定UiReadRequest、Idempotency-Key）与GET /reads/{request_id}，仅Principal提供scope/subject/markings，无角色或租户覆盖。仅显式凭据文件配置后装配，无后台任务；提交202、查询200，业务异常固定脱敏，全部响应no-store。匿名及严格请求拒绝在服务前完成。

新增HTTP/独立连接测试：真实非超级身份与回滚、错误文件/角色拒绝；路由固定参数/tenant/injection/匿名/错误脱敏，无有效连接配置503。旧目录入口回归，规范路由聚合无需新增router模块；实际主库/API尚不升级。

## UQ4-C Web固定读取会话（基线91bb1053，编码前补充）

新增apps/web/src/api/runtimeWorkshopRead.ts和测试。由已解析RuntimeWorkshopEntry构造固定analyst_workspace_view_v1及七字段target，仅caseLimit/runLimit有界可选。捕获当前org/project/subject/roles与内存token，仅比较不输出；调用方必须提供当前资源检查和AbortSignal，前后都核身份/资源/取消。

一个会话至多POST一次，服务端Idempotency-Key固定随机值；POST结果未知不自动重发。已得到requestId后只GET该原请求，响应严格校验schema/scope/requestId/hash/revision/状态/时间/成功结果或失败码，不把客户端校验当执行授权。等待窗口最多60秒、每次HTTP最多10秒；超时保留原requestId，允许继续查询而不创建新请求。调用方离开/切scope/资源撤下必须abort，迟到结果丢弃。

验证单次提交、GET不重发、错误租户/主体/凭据/target/hash/状态拒绝、未知提交不重发、有界等待后同ID继续查询、取消丢弃。本波不挂静态八页面或改变原ExtensionBridge；后继签名UI与实际资源挂载属UQ5。

## UQ5-A 运行签名页面宿主与路由（基线3d3975db，编码前补充）

新增apps/web/src/components/extensions/RuntimeWorkshopHost.tsx及测试，复用ExtensionHost/ExtensionBridge，不另造消息安全协议。宿主key涵盖安装revision、binding revision和原签名身份，变化整页卸载并abort。只接固定analyst读取和有界input；同页已知pending继续GET原会话，未知提交保留原会话不可重发，终态后显式新read才新会话；并发read拒绝。命令/产物下载不提供。

修改api/tenant.ts在token改变/清除时仅派发无敏感内容aos-auth-updated事件；RuntimeWorkshopCatalog.tsx监听并清空重读，key包括当前token的内存比较；迟到旧身份目录丢弃。

随后修改App.tsx全局挂RuntimeWorkshopCatalogProvider、pages/s2/ecommerce/routes.tsx选择已声明runtime页面与原legacy fallback。同canonical route双声明拒绝；runtime路径需当前目录ready且旧目录确定无同路径声明，未知不选。legacy路径按原逻辑继续，无runtime Provider的独立旧组件测试兼容。新增运行目录导航并接AppShell；运行页面使用通用导航头，不借用旧页面专属按钮。上述后续文件在宿主验证后直接衔接。

验证宿主固定桥接/原pending续查/未知不重发/换身份换revision卸载取消，旧ExtensionHost和目录回归；路由/导航验证冲突、无UI、目录未知、旧8页回归。实际浏览器仍需后继签名资源UQ5-B及主库UQ6部署，不以测试iframe证明真实业务。

### UQ5-A2 路由落地细化（基线c9f32927，编码前）

具体修改App.tsx、pages/s2/ecommerce/routes.tsx、shell/AppShell.tsx、nav.ts、components/workshop/InstalledModuleNavigation.tsx及EcommerceWorkshopCatalogContext.tsx。运行目录ready的精确canonical路径选择签名宿主，legacy目录必须ready/empty且无同canonical声明；冲突提示且两个宿主都不加载。没有RuntimeProvider的既有独立组件保持原行为。侧栏沿现有样式追加真实运行条目，不构造假legacy权限DTO；通用NavPage仅需要moduleId/route/menuLabel。签名页面不启用旧八页面专属头部动作。

旧目录保留scope tenantKey合同，但另外捕获subject/roles/authRevision，身份变化清空并重读、拒绝迟到响应；同身份显式reload继续原stale快照行为。所有凭据内容不进key/日志。当前仅canonical入口，legacy别名的runtime映射须由后继签名声明明确后验证，不能硬编码8页假映射。

新增runtime route/navigation测试及旧目录同租户身份变化测试，回归旧8页AppShell/Host/导航/目录；类型检查及真实浏览器检查当前未配置UI时的诚实空态。主库与API仍旧部署，新UI仅在后继签名资源有效后出现。

A2回归核实：基线c9f32927的EcommerceWorkshopHost已使用“当前工作台入口不可用”，但AppShell三处测试仍断言旧“模块未安装”。空目录可能来自未授权或无UI，不能误断卸载；仅修正这些过时文案断言，产品文案不倒退。

A2浏览器复核补充：运行目录空态会复用旧Host，原主区域刷新只更新legacy目录。EcommerceWorkshopHost新增可选onCatalogReload回调，运行路由传入双目录reload，默认不传保持既有行为；增加空态按钮同时刷新两目录验证。

## UQ5-B 后继签名包交付拆分（基线bac0a89a，编码前）

发现现有ExtensionHost仅传nonce，但协议hello要求installationId/generation/executionEpoch；签名子页面不能取得父组件props，必须补公开启动合同。另当前只存在签名资源URL解析器，未发现对应资源HTTP服务，不能把有URL当作能加载。

B1先修改apps/web/src/components/extensions/ExtensionHost.tsx和ExtensionHost.test.tsx：URL fragment精确传aosNonce、installationId、generation、executionEpoch、initialRoute，替换原fragment。不得传token、subject、roles或业务数据，不把公开身份当权限；原桥接继续核对来源窗口、nonce、代次和声明。身份/路由变化重建iframe及nonce，测试URL查询摘要保持、fragment可组成合法hello、旧nonce和旧身份不复用。

B2新增签名资源只读服务设计与实现：按已发布且签名验证通过的不可变包清单解析frontend入口，仅允许声明HTML与精确packageHash/contentHash；拒绝路径穿越、后端文件、未知版本、签名或摘要不符。响应限制脚本网络能力，页面通过原MessagePort读取，不携带API凭据。先完成适配现有Registry/签名加载器的具体方案再编码。

B3为growth 1.7.0制作独立1.8.0候选，保留旧版本原字节与既有数字同事配置，注册analyst_workspace_view_v1纯投影方法；首个真实UI仅声明经营参谋canonical路由，保留七模块贡献和独立operations-base，不用假数据填充另六页。补包协议/页面测试、实际OCI资格验证及新不可变签名树，后继UQ6备份迁移与原宿主部署。B1/B2/B3各自落证据与提交，代码通过不算主库安装或真实业务链完成。

### UQ5-B2a 可信资源读取核心（基线e88cc76e，编码前）

先新增extension_runtime/ui_resource_reader.py与tests/extension_runtime/test_ui_resource_reader.py。固定按publisher/id/version查询已发布Registry记录（参数化），使用现有ReleasePolicy快照校验当前信任根及发布证据。请求packageHash必须等于记录；仅采用记录内唯一content_hash sourceRef加载allowlist包，复核manifest/contentHash/signature一致；前端manifest自身摘要、入口HTML摘要和请求contentHash均必须一致。只允许manifest声明的单一frontend HTML入口，最大1MiB UTF-8；不读后端、任意资源或数据库业务对象。

Registry记录读取和返回前发布状态/当前策略再核验使用新只读事务，拒绝读期间撤销或更换发布事实，不持长事务跨文件读取。复用已有read_verified_artifact防软链接/换文件/摘要失配，不引入普通路径读取。加载器会记录无效签名而非统一抛错，因此明确要求已发布策略验证以及加载签名与记录相等，不依赖“load成功”。

本切片只交付读取核心；B2b随后挂匿名静态代码资源HTTP（不可包含租户业务数据），设置no-store/nosniff/sandbox CSP/connect-src none，校验重复query/路径以及错误脱敏，资源origin显式配置才开启。匿名资源访问不是业务读取授权，业务仍由宿主原身份受限队列核验。

B2a测试落到tests/asset_registry/test_ui_resource_reader.py，以复用该包现有真实Ed25519签名/ManifestLoader fixture；Registry查询用精确SQL与行替身，文件、签名和ReleasePolicy为真实实现，明确不冒充主库发布验收。

### UQ5-B2b 资源HTTP与显式配置（基线2b7a060e，编码前）

新增routers/runtime_ui_resources.py和tests/asset_registry/test_ui_resource_http.py；修改asset_registry/control_wiring.py新增只读Reader builder（connect_read_only inherit_scope=False，仅全局Registry发布资源），domain_manifest.json追加infra路由并运行现有生成器更新domain_aggregates.py。

固定GET /v1/bundles/{publisher}/{bundle_id}/{version}/{entrypoint:path}，仅允许精确两个查询参数packageHash/contentHash各一次。没有tenant/subject参数，没有运行或写入路径。AOS_EXTENSION_UI_RESOURCE_ORIGIN与AOS_EXTENSION_UI_PARENT_ORIGIN必须是无凭据/query/fragment/path的HTTPS或本地HTTP origin；配置缺失拒绝503，不改既有resolver支持外部资源前缀的合同，但本API自身资源服务只支持根origin。

响应text/html UTF-8，no-store/nosniff/no-referrer、CSP sandbox allow-scripts/default-src none/connect-src none/base-uri none/form-action none/object-src none/frame-ancestors精确父origin；仅允许签名HTML内联脚本和样式，不允许外部脚本/媒体/iframe/eval。保留原iframe allow-scripts沙箱，不暴露cookie/token。所有该路由错误脱敏且no-store；未知异常统一503，未声明资源404，格式400。

HTTP验证使用真实B2a签名读取fixture贯穿；检查正常HTML、安全头、未配置零读取、重复/额外参数、路径后端/穿越、摘要错误、已撤销和未知内部异常不泄漏。检查路由生成无漂移及原资源/读取回归。主API部署仍UQ6，不在本波重启原Host或解封九条业务路由。

### UQ5-B3a 包内固定只读方法（基线ea88508f，编码前）

修改bundles/solutions/ecommerce-growth/backend/ecommerce_growth/__init__.py，额外注册analyst_workspace_view_v1（POST /ecommerce/growth/workspace/view），仅接受exact {snapshot}并调用已有analyst_workspace_view.project_workspace。九个业务operation行为不改，不修改旧1.7候选或已安装签名树；新方法注册不解封业务dispatch。

新增tests/extension_runtime/test_analyst_workspace_runtime.py，使用现有真实合同fixture和SDK serve_session register→invoke长度帧贯穿，检查来源引用/只读标志/不变输入，拒绝额外字段和伪造快照，九个原方法保持受限，无上下文business port调用。SDK RegistrationContext没有tenant字段，不新增身份协议；宿主承担当前主体和数据范围，包验证快照内部一致性。后B3b生成1.8候选时仅覆盖已审查entry/projector、加入签名frontend并保留旧1.7其他字节；不把可变source1.3当作当前安装。

### UQ5-B3b1 包内经营参谋页面（基线88949cc2，编码前）

新增bundles/solutions/ecommerce-growth/frontend/index.html（单文件签名页面）和apps/web/src/components/extensions/AnalystSignedPage.test.ts。仅声明经营参谋，页面内容由原MessagePort读取状态中的result生成；无fetch/数据库/外部脚本/图片/存储/命令，所有数据用textContent写入。显示读取时间、真实事项标题、分析类型、Case/Run状态、来源引用与截断提示；空数据诚实呈现。

从fragment解析exact五字段启动合同，校验nonce/UUID/epoch/初始路由。仅接收parent来源且nonce/身份一致的connected与唯一端口；一次握手10秒。连接后首次只读，固定operation+limits；最多一个在途请求，sequence严格递增，响应仅匹配该requestId。成功/失败状态显示；通道错误或90秒无响应封闭本页面不重发，原宿主报告读取未完成时仅允许显式继续查看原会话。pagehide关闭端口/定时器，不接迟到消息。

用真实页面脚本+DOM、受控父窗口/端口测试握手、错误身份零读、在途不重复、安全文本、空态、错误/超时、pagehide；不把DOM替身当浏览器CSP或实际读取证据。后B3b2再冻结frontend manifest摘要、完整候选API贡献/数据范围授权要求，实际OCI与浏览器仍后继。

### UQ5-B3b2 不可变1.8候选（基线b0bd07fe，编码前）

新增scripts/prepare_ecommerce_growth_1_8_candidate.py、tests/extension_runtime/test_prepare_ecommerce_growth_1_8_candidate.py和bundles/candidates/ecommerce/solution.ecommerce.growth/1.8.0/。基线1.7树hash固定2ba9ed424307ca1d4bf379656714705429a3efa93b9657d0a3976bd5fbd3a1b1；只复制当前entry、analyst_workspace_view.py、frontend/index.html，三份源hash固定，目标必须不存在。

保留1.7静态14贡献，候选注册共14+10=24且manifest一致。生成frontend/manifest.json，精确analyst路由、只读方法、空commandClaims；runtime.frontend绑定manifest SHA256，包内HTML由artifact索引签名。permissions.dataScopes新增ecommerce.workshop.read，是安装时需要明确授予的数据范围而非自动给用户授权。更新8个既有workshop/template self bundleRef到1.8，其他文件不改。源package1.3开发manifest不冒充新候选。

验证目标不可覆盖、基线/源hash漂移拒绝、精确文件diff允许列表、六数字同事/模板保持、7+1边界、ManifestLoader读取合同、真实SDK注册与声明一致及投影调用。候选此时未构建/签名/发布；下一波新版本实际镜像构建与资格验证，不运行旧脚本内1.7/niushop1.3常量覆盖当前niushop1.5。

### UQ5-B3c 真实OCI构建/资格验证（基线ab072a46，编码前）

修改scripts/build_ecommerce_runtime_candidates.py：原固定12操作计数提为默认12常量，资格会话可选probe回调在2048心跳后同一session调用；默认无probe保持既有行为/回执。新增scripts/build_ecommerce_ui_candidates.py固定profile选择core1.3、niushop1.5、growth1.8、operations-base1.2，期待13 API/8模块；不能任意跳过清单校验。

新增只读探针fixture与测试：fixture为明确测试Case/Run合同及对应投影，不是真实租户经营证据；profile仅为含analyst_workspace_view_v1声明的growth session附加probe，结果必须逐值等于已冻结预期，回执只记方法、payload/resultHash、Case/Run计数和executionAllowed=false。不调用九个业务方法，不读SSH或生产库，不新造业务Run。

沿现有一次性资源journal、隔离OCI、临时本地镜像服务与签名篡改拒绝流程，构建输出放仓外新目录。修改前后测试默认builder不漂移、新profile准确、probe只在本会话且失败仍释放；再实际build/qualify。原运行三个容器/Host不重启，未知结果先查journal与资源，不盲重跑。

### UQ5-B3d 永久签名准备与发布边界（基线8f533681，编码前）

新增scripts/a0v_ecommerce_ui_signed_successor.py与对应tests/extension_runtime/test_ecommerce_ui_signed_successor.py，私有复用既有signature/verify_inputs/signed_tree流程，固定growth1.8构建回执与新profile，旧根为当前niushop1.5的13版本，新根只追加growth1.8成为14版本。require_sessions严格1/2/24、2048心跳、释放、精确fixture/payload/resultHash和只读标志；源保护加新profile与fixture，旧签名根和已有版本字节保持。

本切片CLI只preflight或prepare签名，不调用旧publish/switch_root/main。代码核对发现RegistryService._assert_publish_duty_separation要求publisher区别creator/validator；旧helper按新名字拼接actor和固定roles不能证明真实主体职责分离，禁止照搬为当前真实验收。当前org-org/dev-project成员仍runtime-owner(admin)与user:dev(owner)，原独立审批身份待核验；不造新成员或假发布人。本波永久签名可独立完成，后继继续备份/迁移/服务升级准备。真正发布/安装要使用可核验现有主体及产品授权，不能靠资格fixture替代。

## UQ6-A 031~035本地主库增量迁移（基线d7c56562，编码前）

部署租约A0V-UI-READ-LOCAL-DEPLOYMENT-20260913-V2，owner m1，至2026-09-17；首次登记文件名校对后已无变更关闭并换正确V2，不篡改旧Receipt。项目强一致投影CURRENT，parent authority仍AOS-000573；不升级总门。

新增scripts/a0v_ui_read_deploy.py与tests/extension_runtime/test_ui_read_deploy.py，复用已验证固定本地连接/指纹/0600写入辅助。固定MAIN aos_meta_head，克隆aos_ui_read_20260913_test，a0v_030→a0v_035精确五迁移链，5秒DDL锁超时/30秒语句超时及迁移advisory lock。只新增读队列/NOLOGIN角色/固定函数及队列最小ACL，不改原表数据和默认ACL，不重启Host。

prepare先备份主库到0700仓外目录中的0600 dump，再新建拒绝PUBLIC CONNECT的恢复副本，核对迁移前版本及关键业务表指纹，升级副本并复核相同数据指纹、空队列、FORCE RLS、11状态列UPDATE/禁INSERT DELETE TRUNCATE及身份列UPDATE、API无表权限、5个固定函数精确EXECUTE角色且PUBLIC拒绝。保留备份/副本/prepare证据，既有目标拒绝覆盖。

apply仅接受完整prepare证明（dump/migrations/script hash一致），主库与克隆仍处于预期版本/数据基线并复核ACL；先落不可覆盖apply-intent再升级主库，读回版本/数据/ACL。已有意图不重跑，须独立readback判断提交结果。API独立登录身份、Host升级、签名包发布安装、浏览器真实读不在此迁移动作内。测试精确版本链/证据防篡改、已有意图拒绝和数据库ACL verifier；再实际prepare/clone验证才apply。

UQ6-A实现补充：新执行器自身protected_write使用0600/O_EXCL、文件及父目录fsync；备份完成后fsync。保留旧辅助不改，防止崩溃丢失执行意图；已有意图只能readback。

## UQ6-B 专用UI读取身份（基线90e89719，编码前）

租约A0V-UI-READ-API-IDENTITY-20260913。新增scripts/a0v_ui_read_identity.py与tests/extension_runtime/test_ui_read_identity_deploy.py，生成唯一技术LOGIN aos_ui_read_transport_20260913（不是业务成员/审批人），NOINHERIT/非超级/无BYPASS/无创建角色数据库/无复制，仅MEMBER aos_ui_read_api，无ADMIN。复用固定受控本地管理连接；密码只在内存与0700目录的0600文件，不能输出或进环境/共享证据。环境仅设置凭据文件路径。

先clone：核035、当前空队列/权限，持久化clone身份文件后创建角色并只授所需角色/CONNECT，用真正ui_read_connection验证当前正租户runtime-owner成员、受限metadata空结果、同连接篡改subject拒绝、canary主体不存在拒绝、直接表SELECT与宿主函数EXECUTE拒绝。已有角色无对应私有身份文件时拒绝重置，未知凭据不重发生成。

再main：要求clone成功证明与035部署证明、当前clone/main核验，通过后仅派生dbname为aos_meta_head的私有文件并真实重复上述读/拒绝检查。前后19关键业务指纹与队列0保持；不发送业务请求，不修改meta_membership/authz_tuple、不造独立审批人、不启动另一个Host。现阶段没有已成功的真实队列请求，不能声称主库跨用户结果交付已验收；该项留真实安装后验证。

## UQ6-C 既有API启动配置接入（基线4c226874，编码前）

租约A0V-UI-READ-API-PROFILE-20260913；修改scripts/a0v_product_controlled_api.py及services/aos-api/tests/test_a0v_controlled_api.py。沿用现有受控API启动/端口租约，Host关闭标志与其他后台写者禁用不变，旧13版本签名根不变。

专用读取身份必须与主库实测证明的数据库、角色、四项拒绝、空请求及文件摘要一致，并用现有严格0600身份解析器核验。文件/证明均缺失时兼容旧未部署场景并清理遗留环境；单边缺失或篡改则拒绝启动。证明齐备后显式设置资源来源http://127.0.0.1:18181及父页面来源http://127.0.0.1:5173。启动preflight用专用连接实测角色、数据库及035缺失请求返回空，输出仅安全元数据。不得将该结果表述为完整生产Web身份或业务安装完成。

测试缺失兼容、不完整拒绝、摘要/权限/证明错误拒绝、环境清理及现有关闭标志；然后实际check通过才以原API租约更换18181进程，不碰原Host，验证健康和页面。

## UQ6-D1 宿主单写者启动锁修复（基线80dddbea，编码前）

检查原Host main发现锁由可自定义status-file派生，可用不同状态文件启动第二Host；锁冲突分支还覆盖正在运行Host状态。修改scripts/a0v_ecommerce_runtime_host.py及services/aos-api/tests/extension_runtime/test_a0v_ecommerce_runtime_host.py，租约A0V-HOST-SINGLETON-RECOVERY-20260913。

本地固定canonical锁为原RECOVERY/state/ecommerce-runtime-host/singleton.lock；兼容锁包括旧默认状态锁和当前运行runtime-host-aa3010c4.lock，额外保留调用者状态锁。稳定排序去重、ExitStack持锁覆盖完整serve。任何锁冲突仅stdout返回HOST_ALREADY_RUNNING，不触碰任何状态文件；参数错误也须先拿锁才写状态。保留原停止排空逻辑、凭据、范围、Host身份、flags，不重启原6606、不启动新OCI。

测试同状态/不同状态、旧运行锁、参数错误冲突均在_build_host/serve之前拒绝且原状态字节不变；测试全部锁直到serve结束持有。实际使用受控空目标状态路径尝试启动，必须在原旧锁处拒绝，不能新建状态文件或第二Host。该拒绝验证通过后再安排真实宿主升级，不能将资格测试等同业务链路。

## UQ6-D2 重启恢复技术分解与D2a真实资源投影（基线5fe8069d，编码前）

原协议证据：preparation_reset只允许applied且无binding、所有资源confirmed released、无已提交verify；当前active实例不可调用。RuntimeHost.stop会关闭preparation owner，资源恢复器不会重建会话。恢复顺序应为：当前exact目标禁入/排空→确认资源释放与未决Attempt结果→依据当前真实权限创建新安装/替代计划并评审→新的runtime-apply/verify/configure/enable→旧新路由切换验证。不得回写旧outbox delivered_at、复活旧owner或继承旧审批覆盖新锁。自动恢复的产品请求与审批承接需后续独立实现，当前不假称已完成。

D2a先修真实状态显示：新增services/aos-api/aos_api/extension_runtime/runtime_resource_health.py，修改runtime_view.py及相关tests/extension_runtime。读取同租户、安装及绑定generation的已提交runtime-apply资源租约；数据库时钟核过期、已释放、cleanup异常、container缺失，空集也不视为可用。该检查只是否定资源存活证明，不代替IPC前后权限与session核验。

RuntimeViewReader在原租户只读事务内为binding收集健康，仅当原推导ready而资源证据不足时输出needs_attention、ui=None、只保留disable并说明需要禁入对账；不改绑定/安装数据库状态，不自动重建、不允许enable绕过。原非ready流程及停用入口保持。资源表缺失依既有runtime_storage_unavailable处理。测试失去资源不调用UI resolver、已释放/过期/缺失/跨租户/其他generation不能撑起ready，健康资源维持原路径，真实PG验证查询。

## UQ6-D2b 当前代际配置选择（基线5f9161c5，编码前）

产品缺口：RuntimeInstallationPanel要求用户手填配置ID/revision/hash。改为从原extension_runtime_configuration不可变记录读取当前安装、当前binding generation的登记配置ref，前端只选择，不手输摘要。该列表是已登记元数据，不是当前四类来源或执行审批已通过；configure/enable仍走原RuntimeConfigurationService当前四来源/权限/CAS/Receipt校验。

文件：新增extension_runtime/configuration_catalog.py；修改runtime_view.py、asset_registry/control_wiring.py、routers/bundle_runtime_installations.py；前端api/assetControl/types.ts、runtimeInstallations.ts、client.ts，pages/s2/assetBundles/readHooks.ts及RuntimeInstallationPanel.tsx、pages/s2/AssetBundlesPage.tsx和相应测试。不得增加新的配置权威或复制策略正文。

GET /v1/bundle-runtime-installations/{id}/configurations：当前Principal角色须原APPLY权限并通过现有installation_reader权限/markings；在同租户读事务重核当前binding代际及revision，参数不允许用户指定租户或generation。按configuration_id/revision稳定取最多51条，返回50条+hasMore真实截断；完整_decode验证摘要但响应只含ref、isCurrent。返回安装revision/etag、generation/bindingRevision供前端选择与确认绑定；无绑定为空列表、不能伪造选项；漂移409。所有返回no-store。

前端复用既有带租户/身份失效保护的readHooks，当前选择仅在列表与运行状态的安装/代际/修订匹配且不stale/refreshing/offline时提交。切换安装/身份/代际清空；选择不可在新列表里匹配时关闭确认。无配置显示需先登记配置，不暴露手输Hash替代。配置创建与四来源自动装配另切片，不能声称此列表已完成全配置流程。

测试：真实SQL隔离/摘要篡改/有界列表；HTTP只用当前主体/角色与no-store；前端选择带exact ref、列表失效不提交、跨代际清空及原disable/enable路径回归；最后主库只读核对现有已登记配置，API部署后浏览器验收。

D2b实施核对修正：原通用useAssetRead仅有请求序号、无完整身份失效保护；本切片不扩改全部旧读取，新增配置读取封装，携带租户/subject/roles/authRevision本地key并监听身份变化，响应前后重新比较；返回旧key的数据立即隐藏，确认按钮提交前再次isCurrent检查。新增operations.ts接口合同条目。

D2b浏览器验收补充：当前真实实例ready，只允许disable，因此不应为打开configure对话框而停用。补运行面板只读的已登记配置概览，使运行中也能看到列表读取成功/无权/为空/待刷新及当前绑定标记；不增加动作。

## UQ6-D2c 四来源装配组件（基线45e6211f，编码前）

沿用A0-V主任务租约。修改services/aos-api/aos_api/aip_runtime_configuration_sources.py，新增services/aos-api/tests/extension_runtime/test_configuration_assembly_pg.py。复核231-9与D2恢复顺序：配置来源装配只是正式登记的前置组件，不等于配置审批、安装恢复或真实首链完成。

输入为当前租户、精确runtime policy引用及非空、最多64个精确职责计划引用；不得硬编码租户、策略ID、角色profile或自动选“唯一角色”。从当前runtime policy派生data引用，从其当前budget policy派生budget revision引用。复用本模块原权威加载器和四来源校验，包括职责冻结、完整摘要、当前head、生命周期、数据库时间有效窗、network/egress绑定及预算规则。要求原aos_runtime事务和租户GUC；无写入、无commit、无权限授予，不创建配置记录。返回原ConfigurationDocument，后续登记和configure/enable必须重新授权，不能缓存本次结果当执行许可。

测试真实隔离PG：正确装配与原四引用精确一致；职责/策略头变动、各依赖过期/撤销/摘要错误拒绝；跨租户、特权连接、空/重复职责拒绝。只读装配仍会持有原权威共享锁直到调用者事务结束，调用者必须短事务且不跨外部调用。产品登记命令、Receipt和Host承接留下一切片，不让API直写配置表。本波次不重启Host、不改变当前实例配置。

## UQ6-D2d 产品配置命令交接合同（基线df1804a8，编码前）

### 已核实缺口与边界

RuntimeConfigurationService.request只接受configure/enable且依赖已登记configRef；build_runtime_control_plane使用默认PostgresInstallationStore连接，而原四来源适配器要求current_user=aos_runtime。因此仅加网页登记按钮不能闭环，禁止给网页复用Host凭据绕过。append_configuration已有原不可变记录、幂等、exact代际/CAS、当前权限校验；保留为唯一配置记录写入实现。

### 实施切片与原任务映射

仍属原D2恢复与BG00/BG01前置，不新增总进度分母。

1. D2d-1：配置登记请求合同。新增extension_runtime/configuration_stage_contracts.py及对应测试。固定stage-configuration动作、精确安装ID/etag、generation/bindingRevision、非空有界roleRefs和policyRef、可选previousRef；只接受原AIP职责/策略authority。客户端不能传subject/tenant、任意data/budget或payload、权限、deadline、requestId、状态。凭当前服务身份写subject/scope，服务生成请求ID/数据库deadline。拒绝重复职责ID（即使revision不同）、布尔版本号、非法UUID、未知字段。绑定目标和来源整体成为请求摘要，不自动刷新后重投。
2. D2d-2：新增隔离交接队列及原宿主消费者；迁移需另列精确文件与DDL评审后实施。状态requested→succeeded/rejected/expired，不引入跨事务外部Attempt：宿主锁请求后，在同一短事务锁installation/binding→重新查当前成员/markings→装配四来源→append_configuration→写固定configRef结果。数据库事务回滚可安全重新领取，commit后结果读取不重复登记。无法确定commit结果时只读原请求；不创建第二key。请求到期或目标漂移直接终态拒绝，不能自动换目标。请求及结果只属于原租户原subject。
3. D2d-3：专用API技术身份/固定SECURITY DEFINER提交与查询函数，API无配置表/队列表直接权限、无Host身份可达。受当前Principal控制，当前成员/markings检查须在SQL入口或可信权威事务执行；限制有界待处理量、固定期限，所有响应no-store。调用成功202只表示收件，结果仅固定ref，不能配置/启用实例。
4. D2d-4：正式配置来源选择与登记UI，旧配置列表立即可回读新ref。提交后GET同请求，不靠前端重发；身份/安装/代际/etag改变清空选择，失效后不展示旧结果。网页给用户可读职责/策略名称，不要求手填hash。真实配置/enable仍需单独命令，不合并自动启用。
5. D2d-5：当前configure/enable从Web到Host的同类身份交接。不得给旧service注入伪连接劫持commit以强拼事务。必须保留原execute_idempotent Receipt，证明同请求Host重入复用结果且授权撤销后不返回旧执行许可；另写具体事务设计再编码。
6. D2d-6：部署前克隆/备份/ACL否定验证，维护原Host单写者。Host实际替换必须结合D2的新代际恢复与当前exact评审，不盲停6606。真实浏览器完成登记→选配置→configure→enable→读工作台才算该产品流程验收。

### 退出条件与风险

D2d-1合同或D2d-2隔离PG测试不算D2d产品流程完成。禁止提前启用迁移或flag，不改当前安装/旧13包根/业务路由。API排队拒绝、身份撤销、旧generation、过期、重复key冲突、事务中断/提交未知、同租户不同subject结果隔离都须有数据库证据。实际权限来自当前成员记录，不能用材料中的角色名或历史脚本伪造审批人。

### D2d-2a 空交接表与不可变边界（基线16a144ec，编码前）

新增alembic/versions/a0v_036_runtime_configuration_stage.py，专用租约A0V-CONFIGURATION-STAGE-SCHEMA-20260913；新增tests/extension_runtime/test_configuration_stage_schema_pg.py。只在隔离PG装载，主库仍035。本切片只创建空表与守卫，不授Web/API提交权限，aos_runtime仅SELECT及固定终态字段UPDATE；无DELETE/TRUNCATE/身份修改权。

表extension_runtime_configuration_stage_request存原scope/subject/key、精确installation/generation/etag/bindingRevision、固定请求JSON与canonical请求摘要、created/deadline、state/revision/completed/result/failure。租户FORCE RLS，scope+subject+key唯一，绑定FK。requested只能一次转succeeded/rejected/expired，终态/身份不可变。初始精确target须与当前binding/installation一致；成功结果须引用同租户/安装/代际、同actor的原configuration确切ID/revision/hash，不能用其他主体记录装成功。SQL边界验证JSON固定字段与原AIP引用；canonical函数复用原Asset Registry定义。TTL最多5分钟，未到期不能expired，到期不能成功。API收件权限、限流、原主体查询和宿主授权承接下一切片；本表成功guard不是权限授予，不能单独发布。

验证：隔离PG原配置记录成功关联、伪结果拒绝、跨主体拒绝、CAS漂移初始拒绝、身份/终态/DELETE/TRUNCATE不可变、输入JSON/摘要篡改拒绝、RLS负租户和最小列级权限。数据库单事务登记与回执回滚由消费者切片另验。

### D2d-2b 原子登记消费者（基线b0f780fc，编码前）

新增extension_runtime/configuration_stage_consumer.py及对应隔离PG测试，沿用主A0-V租约。第一步实现可由原Host调用的process_one事务组件，不立即改Host装配或重启。入口要求aos_runtime当前scope事务、可信ConfigurationAuthorization对象；不能从HTTP注入回调。只处理本租户requested最早请求；先读候选，再依原锁顺序锁installation，最后FOR UPDATE SKIP LOCKED重取候选且确认仍requested。源document由D2c固定装配，不接受客户端data/budget。

使用子事务装配+append_configuration+成功结果，任何可解释的来源/权限/目标拒绝回滚子事务中的配置并在外层标记固定REJECTED代码；未知数据库错误直接抛出、整个事务由调用者回滚，不自动映射成功/不吞掉故障。到期直接expired；配置幂等键固定configuration-stage:<requestId>；成功结果只原configRef，revision从1到2。同事务数据和结果确保中断可重领、成功不重复。组件不自行commit、不调用外部系统、不启用运行。测试回滚中断、成功后不重领、权限拒绝/来源失效/CAS变化无配置、篡改请求摘要拒绝，真实四来源与原append_configuration均参与。

这一步测试许可使用隔离测试权限表，必须标为隔离权限夹具而非真实用户授权；当前正式CurrentConfigurationPermission的真实安装锁集成以及Host装配另验，不能据此宣称真实登记功能上线。

D2d-2b入口补充：同模块新增ConfigurationStageConsumer正式包装，构造仅接受原CurrentFourSourceConfigurationAuthorization精确类型，不能用测试callback替代。run_once复用consumer_connection独立IDLE/事务/当前runtime非特权身份校验，并对新增队列与原配置表检查FORCE RLS、非owner身份。底层process_one仅为已持事务组件；正式包装不做任意权限注入。先验证构造拒绝，再另切片接原Host类型白名单/feature flag。

### D2d-2c 原Host默认关闭装配（基线85291892，编码前）

修改runtime_host.py、production_runtime.py、asset_registry/control_wiring.py，新增configuration_stage_preflight.py及测试。RuntimeWorkerDependencies增加严格bool configuration_stage_enabled=False；环境AOS_EXTENSION_RUNTIME_CONFIGURATION_STAGE_ENABLED仅缺省/0/1，异常配置拒绝组装。原租户assignment有开关才加入唯一ConfigurationStageConsumer；保留旧configure/disable/UI consumer顺序与行为。

开关打开前检查public交接表/原配置表存在且FORCE RLS/非owner，runtime无INSERT/DELETE/TRUNCATE及身份列UPDATE，只允许五个终态UPDATE字段；配置表保持原INSERT权，守卫触发器完整启用，guard为非SECURITY DEFINER。missing/expanded ACL拒绝Host选择，固定CONFIGURATION_STAGE_PREFLIGHT_FAILED。不让开关自动迁移或开户，不启动另一个Host。原Host未替换、主库035不能开启；测试只构造/隔离SQL验收。

### D2d-3a 受限收件与原主体查询（基线87ec28bf，2026-09-14编码前）

迁移租约A0V-CONFIGURATION-STAGE-API-SCHEMA-20260914：新增a0v_037_configuration_stage_api.py及tests/extension_runtime/test_configuration_stage_api_pg.py。主库不应用，先隔离验证。

新增NOLOGIN技术角色aos_configuration_stage_api，无其他角色继承，不授任何配置/队列表直接权限。仅执行固定principal/enqueue/query函数，固定search_path，拒绝PUBLIC。调用者须非特权session_member且SET LOCAL ROLE精确技术角色、READ COMMITTED、scope/subject GUC一致；当前成员唯一且admin/asset-installer，不能以owner替代安装权限。入口不接受客户端roles/markings。原当前installation revision与composition lock读回permissionDiff；核对diff摘要与lock payload中的副本、installation锁引用，逐一读当前marking授予。Host仍做原完整lock/source/权限核验。

enqueue：精确normalized ConfigurationStageRequest（含previousRef:null），当前成员/安装标记后按租户advisory lock串行限制64个tenant/8个subject未决请求。subject+key唯一，同key异内容拒绝，同内容只返回原receipt；不得因旧target变化重新排队。服务生成UUID与数据库3分钟deadline，原036守卫校验JSON/目标/摘要。返回requestId/requestHash/state/revision/deadline，不返回配置正文。

query：当前成员重新核验，按scope+subject+requestId读取；不存在/他人请求返回null，存在再核当前安装标记，返回固定metadata与configRef/失败码。权限撤销不能读取旧结果。不存在Host启动、能力调用、配置/enable行为。远程OpenFGA模式必须在后续API连接层拒绝并等待相应adapter，不将本地SQL权限当远端授权。

测试先构造隔离原表/锁引用和角色session，验证成功收件/重放/冲突/容量，原主体查询/其他subject/负租户/角色撤销/缺marking拒绝，直接表访问拒绝、特权session拒绝；随后运行036边界回归。新SQL权限检查是收件/读取门，不能替代Host完整当前授权。

### D2d-3b 受保护连接与HTTP（基线72cd9a69，编码前）

沿主A0-V租约。新增restricted_api_identity.py，把既有ui_read_connection.py的0600/无符号链接/无FIFO/重复JSON拒绝和数据库LOGIN/NOINHERIT/单一逻辑角色/无ADMIN权限校验抽为共用实现；旧UI保留入口和错误合同，跑原连接回归。新增configuration_stage_connection.py使用独立环境路径AOS_RUNTIME_CONFIGURATION_STAGE_CREDENTIAL_FILE、schema aos.runtime-configuration-api-identity/v1、固定逻辑角色aos_configuration_stage_api；不得读其他DSN或role兜底，OpenFGA远程配置时拒绝本地adapter。

新增configuration_stage_http_service.py：调用037固定函数且在连接context提交后才返回；只接受当前scope/subject和原请求模型。查询不存在变404。SQL权限错误403、同键/目标冲突409、数据库或提交未知503且提示保留原请求键查询，不自动重投。HTTP返回固定schema和tenant、receipt字段，JSON no-store，不返回SQL/DSN/内部错误。

新增routers/runtime_configuration_staging.py并作为原bundle_runtime_installations子路由纳入：POST /v1/bundle-runtime-installations/configuration-requests，GET同路径/{request_id}。body精确来源合同、不接客户端tenant/subject/roles/markings；require_principal与原APPLY角色门，数据层再核当前成员。缺凭据503，所有成功/拒绝/验证/异常均no-store。测试非法字段/匿名/角色、当前主体来源、受限身份文件及真实隔离LOGIN角色、旧UI连接回归；不部署API或主库，先完成受控组件。

D2d-3b实施复核：FastAPI先把JSON解为Python数组，原严格tuple字段使合法roleRefs被400拒绝；只增加list→tuple的容器适配，引用值/上限/唯一性校验不放宽。另发现收件commit成功但响应丢失时客户端可能不知道服务器requestId，当前GET按ID无法找回；下一切片新增按原subject+Idempotency-Key只读找回入口，不重发POST，也不凭未知结果换键。

### D2d-3c 未知提交的只读找回（基线7d07a361，编码前）

迁移租约A0V-CONFIGURATION-STAGE-LOOKUP-SCHEMA-20260914：新增a0v_038_configuration_stage_lookup.py，按原scope+subject+key读request_id后复用037 query权限与结果。不存在返回null，不INSERT/UPDATE，不调用enqueue；查到请求仍需当前成员及当前安装marking通过。

HTTP新增GET /v1/bundle-runtime-installations/configuration-requests/lookup，Idempotency-Key请求头（不把key写URL），静态路由必须在/{request_id}之前登记。Service.find只读lookup函数，返回原固定status；无记录404仍不重发，连接未知503继续查询原key。测试已收件模拟响应丢失后找回同ID/请求数不增加、不同subject不可查、撤权拒绝、未知key不写入，HTTP静态路由/当前身份与no-store；未部署主库。

### D2d-4a 只读来源目录（基线14a8186e，编码前）

复用原RuntimeViewReader只读连接及installation可见性/APPLY角色门，不给037技术角色增授源表权限。新增extension_runtime/configuration_source_catalog.py；修改configuration_catalog.py抽出同代际目标核验供两个目录共用，runtime_view.py、control_wiring.py、bundle_runtime_installations.py追加GET /{installation_id}/configuration-sources。

返回精确当前installation/etag/generation/bindingRevision，以及本租户当前frozen职责计划和active且未kill的运行策略各最多50项+各自hasMore。每项仅原sourceRef和来源标签（职责profile、策略原标识），不返回策略正文、模型凭据、预算金额或授予任何执行权。目录是候选，不承诺全部依赖有效；登记时原四来源/权限重新验证。无binding返回空；目标前后核对，变化409，所有响应no-store。目录摘要形状非法拒绝而非替换；只读候选不能被当成审批。

验证原目录回归、真实隔离PG当前head/生命周期/租户/有界目录，HTTP当前Principal及无缓存，主库只读目录核验后再接前端来源选择。当前功能不修改主库来源、配置或绑定。

## D2d-4b 产品配置登记交互（基线6e85af18，编码前）

沿用原安装管理页，不新增业务工作台。先落前端来源/请求协议和客户端，再接独立配置登记组件：读取当前职责和策略，选择后提交精确来源引用，服务端推导预算和数据引用。登记不等于绑定或启用；成功后刷新原已登记配置列表，继续原 configure 审查流程。

修改目录：apps/web/src/api/assetControl（configurationStaging.ts及测试、client.ts、operations.ts）；apps/web/src/pages/s2/assetBundles（readHooks.ts、新登记组件及测试），接入AssetBundlesPage.tsx。复用原身份指纹和HTTP请求器；不新增直接数据库访问，不调用Host管理命令。

严格校验候选目录目标与当前安装/代际/etag/绑定修订。身份、租户、授权修订变化立即隐藏旧来源，提交前再次检查。每次明确登记生成一个请求键；提交后未知结果只能GET原键找回，禁止自动重新POST或换键。回执严格验证租户、状态/结果关联；原请求ID已知时必须匹配。请求仍处理中允许有界只读查询并显示等待，不将超时视为失败或完成。持有未决请求时禁止再次登记。

请求恢复状态仅保留当前页面内存，不持久化来源/身份到共享浏览器存储；页面卸载前用户需保留原请求键，提供手工原键找回输入，不自动提交。切换身份不显示前一身份请求。独立测试真实异常路径：丢响应后只读找回、重复点击不双发、晚到响应/身份切换隔离、目录目标漂移、已拒绝/过期/成功的不同处理。后端尚未部署必须如实呈现不可用，不能模拟成功。
