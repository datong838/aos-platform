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
