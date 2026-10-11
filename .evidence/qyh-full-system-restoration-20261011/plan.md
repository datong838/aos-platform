# 栖月汇电商域全系统恢复执行方案

2026-10-11用户明确授权今天恢复栖月汇租户全AOS系统和数据卷、全量重启及纠正偏离电商域配置。唯一m1 thread；原current159维护Task保留拥有当前preview，当前已恢复名称但无历史data，禁止拿该名称检查点当整系统通过。

## 原数据卷加载
固定prepared container9e8e903010304d33a801065e96c38693c9cbdc7687b7fd35a76e2fe8dbb7ae82/image7e7db...，namedvolume aos-qyh-history159-prepared-data-20261011/database aos_meta_head/cluster7695302940039200809/schema159；原全647表恢复与roles/ACL/sequences已独立验收。再次private0700/full一致backup0600与第二校验副本、全表fingerprints/权限目录/配置备份、before/after/零其他活跃连接核对。原092/原preview/所有备份和卷保留。

先只读准备独立安全transport：新有限LOGIN(role qyh_restored_api_login)仅NOINHERIT/NOSUPERUSER/NOBYPASSRLS/成员aos_runtime、不授owner或直接表权限；私密passfile，不进args/env/日志/receipt。原hba/config保留；新只读hba指定此LOGIN/SCRAM、host loopback18446，无其他host用户/不使用trust暴露。维护窗口先停原none-network prepared容器，确认无进程并占用隔离网络端口后，新容器 qyh-restored-pg-20261011 使用同一数据卷与只读hba；不能两进程挂同PGdata；旧容器保留stopped，无rm/删卷。

加载后回读原cluster/schema/647table fingerprints/roles/权限/命名卷、端口与启动时间。恢复卷org-org的一行name按fresh metadata CAS恢复栖月汇商贸有限公司，不改变租户id/workspace/其他业务数据。新增LOGIN属于明确维保transport，不能作为正式Owner/业务权限证据；API正式身份/OIDC仍沿原门。

## 当前包、安装与API/Web
使用新core1.4.3+platform1.23.0+Growth1.13.0+operations1.2.0实际资格产物，旧core坐标不覆盖。签名入口已核验但未签；新local候选签名也不自行授正式Root/安装/运行。原产品resolve/lock/approve/apply/verify/configure及currentSource/Owner授权逐项对账；恢复Canonical407资源与ef5原历史/899旧12Run分离，旧unknown效果不重放或fake retirement。

新增独立scripts/a0v_qyh_restored_http.py与专项tests，复用原签名/current release/有限LOGIN/OIDC/worker关闭，精确目标和当前schema/generation/tenant门，先RED再最小实现。原preview入口不改；不要更换旧常量绕过门。若旧配置预算expired、binding disabled，不能直接改enabled/fence制造8目录绿。八入口隐藏的原产品行为需按产品/技术方案解决当前安装/configuration/真实resource准备，而非改test结论。

最后维护时序PG→最新m1 API→Web，真实浏览器栖月汇组织选择/默认工作区、8页面与核心只读交互、签名/安装/禁入/canary证据；保留可查看浏览器。运行Host/Provider只在正式身份/Owner/8config/current审批预算完整后开启。全Task仅到真实验收才Delivery，局部checkpoint不宣称完成。

本接续波新增当前安装只读选择入口，精确修改scripts/a0v_qyh_restored_http.py及services/aos-api/tests/extension_runtime/test_qyh_restored_http.py。复用原read_current_installation_release_evidence及其tenant/lock/Registry status/验签/currentness校验，再限定已选定四坐标（core1.4.3/platform1.23.2/Growth1.13.0/operations1.2.2）与当前m1 schema。不得把构建诊断的PUBLISHED投影用于真实安装读取。CLI只有提供安装id/签名根/公共trust根完整参数才进入只读选择；默认库存预检不变、无serve或写操作。

方案核对发现原runtime-image evidence读取要求有当前live resource leases；API全workers/Host关闭的预备阶段不能以此门强迫先开Host。故本步骤仅采用原安装release evidence（不要求live Host），离线镜像/schema诊断证据单独保留；报告显式apiStartAuthorized=false/runtimeHostEnabled=false/currentConfigurationVerified=false。后续正式有限身份/OIDC、安装配置、受支持进程切换和真实八页面仍是独立验收，不删原门。

RED：旧Growth/错误基础包/漏包多包重复包/跨tenant/错误安装id/旧schema及伪造start授权均拒绝或不授予。专项相邻包含原preview与current-installation evidence测试；真实恢复库对当前三个已登记叶只读审计，不新建安装、不重发publish，不伪造正向验收。

本接续调查两个已登记候选：①三个历史叶的ConfigurationDocument/current Source head及预算窗口精确核对，已获用户恢复/元数据只读授权，独立于发布账号；②原产品当前版本安装/configure入口，整体施工已授权，但依赖两新版本真实publish与当前Owner/Source权限，不能先执行。选择①，同轮实际READ ONLY读取恢复卷并用原configuration_store._decode核完整不可变hash；静态白名单Source表/参数化SQL只取ref/head/lifecycle/effective窗口，不读商城源/凭证/业务payload、不修改配置或续预算。

新增仅本Task证据文件audit_restored_configuration.py与脱敏报告/复核文档。输出各类refs数量与hash、当前头匹配及预算有效性，区分4类ConfigurationDocument引用与8工作台界面，不能把旧配置解码当八配置运行授权。所有Ref只作为恢复资料，不伪造当前身份/Owner，不因过期而直接改有效期或fence。无需为一次只读调查写实现镜像单测；验证用真实数据库原解码与当前head对账、前后配置binding元数据精确保持。

## 未知与回滚

受控入口提交后必须生成新的冻结候选，以包含本轮已提交scripts/tests；旧6763文件候选保持不覆盖。freeze_current_api.py增加--receipt-stem（受限文件名、默认原值不变），每次source目录仍以精确HEAD命名且O_EXCL，已有intent/结果/目录一律拒绝；续冻只在新HEAD且新receipt-stem运行。旧与新候选均保留；元数据提交不能把旧候选误称新代码通过。

下一施工步骤为受控HTTP启动接线：精确修改scripts/a0v_qyh_restored_http.py、services/aos-api/tests/extension_runtime/test_qyh_restored_http.py。只增加显式--serve-limited及冻结候选参数，默认只读inventory/current-installation行为不变。复用原外部OIDC合法性门、有限LOGIN/当前647表库身份、原真实published安装release reader及四包选型门；校验冻结报告、6763文件manifest和0700/0600权限，再以当前m1已提交API文件的Git blob逐项对照冻结API，原关闭开关来源亦必须与当前提交一致。不得启动混入其他未提交API改动的源码。固定loopback18080候选端口必须空闲，保留原8080/8434；关闭所有原worker/Host/migration，强制external-only/dev off，PG密码只走私密passfile，清除继承数据库身份和PYTHONPATH，子进程仅加载冻结API。启动本身不授运行Owner/预算/正式配置/八页面通过；生产请求仍经原认证和租户权限，Host及Provider始终关闭。正式登录/独立发布仍未齐备时仅通过原门真实拒绝，不启动候选服务。先RED覆盖缺失/非法OIDC、端口冲突、源码漂移和危险继承环境，再最小实现与专项/相邻验证；mock只证明入口拒绝顺序/环境构造，不能当真实安装或API启动验收。

API准备独立候选：新增本Task证据目录freeze_current_api.py。从精确当前m1提交导出services/aos-api和scripts到本Task/private下0700冻结目录，普通文件0600、git归档逐文件hash核验，不复制工作树其他未提交改动或.env/凭据，不修改原preview入口/进程/端口。核冻结源码原main语法及全部显式ENABLED开关由原preview关闭配置覆盖，Host关闭、migration disabled、dev登录禁用且external-only；这里只保存无凭据启动配置参考，不启动API、不注入正式OIDC、不授Owner。完整结果绑定代码commit、文件manifest hash、具体源码与原开关。未来正式启动必须重新核当前代码和安装/身份/配置，不把本候选称为最新运行中的API。整套授权继续；当前正式OIDC配置来源待用户补齐。

本轮追加只读配置依赖与旧执行记录关联核对：在同一证据目录新增audit_restored_configuration_dependencies.py。使用当前有限LOGIN和READ ONLY事务读取当前runtime policy的五类策略引用及有效窗口；仅汇总三个历史安装关联的Schedule/Run状态和operation状态，不读取业务payload、不调用旧执行器。原正式reader包含FOR SHARE锁，禁止为了在只读调查中调用它而去掉锁或改用可写事务；本次只做元数据候选审计，明确不等于正式reader准入。产出新配置恢复输入清单，旧不可变配置、预算、绑定及Run均保留。

2026-10-11当前发布来源核对后的安装选型：两个已发布基础包使用现有较新平台1.23.2/operations1.2.2（a0v-local-ecommerce-recovery-v2），与新core1.4.3/Growth1.13.0组合。平台源除version、构建lock/image/SBOM/signature外逐文件相同；operations除version、bundleRef及signature外逐文件相同。需逐项核验已有Registry manifest/artifact/content/signature与保留树精确相等，不能因为contentHash相同更写旧1.23.0/1.2.0签名。新core/Growth只在新坐标由现有RegistryService create→validate→publish；所有旧记录与安装保留。采用登记的有限LOGIN与SET ROLE aos_runtime进行本地维保，actor明确为用户授权维保代理，不冒充正式OIDC/业务Owner。

实际职责分离门：core1.4.3与Growth1.13.0均已由原Registry create+validate；Core同actor的publish被DutySeparationRequiredError拒绝。只读回读两个新版本均validated且无published事件，平台1.23.2/operations1.2.2原published签名精确一致。647表指纹仅五个Registry表发生预期登记变化，其余642表精确保持。请求用户提供独立的现有发布身份，禁止仅换actor字串伪造独立身份。等待期间仅沿独立授权继续来源兼容、安装/浏览器恢复准备；不重发已完成create/validate或拒绝的publish，不改变Goal。

已登记独立目录接线Task qyh-restored-bundle-alias-20261011，修复production allowlist对新不可变alias a0v-qyh-current的识别：仅使用原AOS_BUNDLE_ROOT，不增任意根或权限。90项专项/相邻通过，原有权限连接桩失败独立登记；真实Core/Growth签名树由production映射加载验签且源文件不变。下一安全步骤准备四选定版本的唯一公共bundle目录，文件哈希逐项相同、合并公共信任根、不复制私钥；再做混合版本真实镜像/schema资格验证。这些准备不授发布/安装/业务执行，不把七Growth模块加一operations模块的包解析当八页面验收。

选定公共目录现已独立完成：selected-public-bundles下仅4个精确版本；production两个alias同一根、现有ManifestLoader/ReleasePolicy逐包验签；179个原文件逐文件hash和签名保持，8模块解析。未复制私钥、未修改全局配置/数据库、未启动API。准备脚本首次读取manifest错误字段在intent/目录创建之前失败，核对原BundleManifest.metadata后修正；没有重放外部写。selected-public-root-terminal.json明确mixedImageQualification=false/eightPagesAccepted=false，不继承原1.23.0/1.2.0资格报告为1.23.2/1.2.2组合通过。

下一实际资格步骤新增qualify_selected_candidates.py（仅本Task证据目录）：原resolver固定四坐标，原ReleasePolicy/RuntimeArtifact admission核已缓存精确镜像，原SchemaRequirement/require_installed在有限LOGIN的READ ONLY事务核现有schema；三隔离OciDriver会话按原诊断助手登记/heartbeat/清理，无网络、只读root、无真库mount、无Provider/业务调用。candidate资格策略使用原构建诊断ReleaseRecord投影，不声称Registry已publish；真实Registry两版本validated事实保持。每会话原工具一用journal，若未知容器结果只inspect不重发。输出明确fixture/diagnostic only，不能授Host或安装/运行/八页面权限。

该混合组合实际诊断现已通过：三个精确本地镜像admission、原resolver四版本、恢复647表库READ ONLY三个installed schema receipts符合；三个网络none诊断会话各2048次heartbeat及声明精确登记，清理成功并独立inspect确认资源已不存在，179文件不变。mix-candidate资格首次在加载前冻结时间，被原证据currentness门拒绝、intent和容器均未创建；改为读完所有包后冻结统一评估时间，没有降低原currentness规则。证据mixed-candidate-qualification-terminal.json与mixed-qualification-independent-cleanup.json。Registry两新版本仍未publish，独立发布身份/正式安装配置/API/Web/八页面仍待；这是真实缓存镜像诊断，不是自然业务首链或正式Host运行。

在本Task目录新增release_transition.py、只读preflight证据、有限两版本发布intent/terminal和fresh全库备份（private0600及第二校验副本）。public trust根只合并现有v2与新candidate公钥，不复制私钥，不改全局配置。Publish不自动安装/启Host/授权业务；必须后续当前安装、配置、API、浏览器与实际镜像/schema组合资格门。只有预检证明新坐标不存在、旧2个版本完全匹配、身份/头/Task/无未知操作符合时才能apply。已有intent按结果对账，不能重发。

2026-10-11加载实测修订：Colima未挂载本机/Users配置路径，原docker run退出125；只读inspect证明目标不存在、原容器已正常停止。限定LOGIN已完成且不重放。改用docker create同一命名卷、docker cp无秘密hba到容器root拥有文件（postgres仅可读）、docker start；不依赖主机bind、不改变原卷配置。创建/复制/启动各自记录intent与terminal，失败只读对账。
每次操作intent/terminal。未知只读核对，不重试写；没有运行记录不代替证明。新transport失败先停新候选，不删旧容器/库/卷；原preview仍维持原identity和数据。恢复历史卷不改变original092。API登录/运行门失败只限制该动作，继续安全恢复主线。

## 当前恢复身份来源对账

### 只读恢复服务目录依赖补齐（2026-10-11 r3）

真实18080 GET复现：ecommerce-workshop/modules=500 INTERNAL；runtime-workshop/modules=500 REGISTRY_INTEGRITY_CORRUPT。前者original build_ecommerce_workshop_catalog固定repository_root/bundles，原冻结仅services/scripts导致FileNotFoundError/allowlist root does not exist；后者安装/资源门独立，不因前者修复放行。

精确修改本Task freeze_current_api.py，git archive同一当前m1提交的services/aos-api、scripts及bundles，不创建空包目录、不改product loader、Registry、配置或预算。1827个已提交bundles文件逐项纳入原hash manifest，保持0700/0600与排除.env/非普通文件。先保存现有真实500为RED，固定Git blob与归档hash核验，提交后产生新候选；新intent后仅停任务所属18080 API并以原fresh interpreter入口启动，18434及原8080/8434保留。实际HTTP普通目录应200原真实结果（可为空，不等于八页恢复），runtime结果如实保留并继续调查；浏览器重新验证栖月汇组织、135安装、只读405及canary404。不覆盖旧候选/未知结果、不复制私钥、不访问商城源。管理目录恢复属于既有全恢复Task中间步骤，完整目标仍ACTIVE。

### 本机只读管理接入（2026-10-11增量）

实际8080公开/v1/auth/oidc只支持dev，Web tenant.ts默认Bearer dev；方案132保留非生产登录。原restore脚本external-only仅适用于正式受限运行启动，不应阻止已授权的本机管理查看。新增明确管理只读模式，保留原serve-limited所有正式身份与四包门不变；不发token、不伪造publisher/Owner、不开放runtime目录或执行。

修改仅scripts/a0v_qyh_restored_http.py及test_qyh_restored_http.py：显式--serve-management-readonly，同一精确恢复卷有限LOGIN、当前冻结API源码/表头预检；固定127.0.0.1:18080，不接管8080/8434。管理ASGI外层仅放行GET/HEAD/OPTIONS，拒绝所有mutation及WebSocket，在原鉴权之外加门；数据库options强制default_transaction_read_only=on，再核有限LOGIN的新连接实际SHOW transaction_read_only。清除继承AOS_*、PG*及PYTHONPATH/HOME，只白名单恢复worker全OFF、迁移disabled、mock0、dev非生产登录及公共包根，不继承其他专用发行/消费/Owner凭证。不可把数据库默认只读单独作为命令禁入，因此HTTP层拒绝所有写方法，执行worker也必须关闭。

RED→GREEN验证写请求在鉴权/路由前拒绝、WS拒绝、读请求与lifespan正常传递；原formal start和签名/current source门累计不回退。实际只读PG核身份、事务只读，再冻结已提交API、单进程启动，GET组织/安装/运行状态，POST拒绝与canary隔离。全库不写、runtime不准入、原服务保留。管理入口成功只是全恢复中间步骤，正式登录/资源/八页仍待真实验收，不能替代用户完整目标。

仅新增本Task evidence/identity_route_audit.py及脱敏result、verification、review；不修改产品/正式身份/数据库配置。候选一现有身份和启动配置的主线补齐，候选二已登记固定验证器语义闭合；先主线。白名单只读meta_membership结构与org-org/dev-project成员聚合，不读凭证、邮件或业务payload，不把成员记录当OIDC认证/发布授权。docker两现有context只取身份服务名称/镜像/状态/端口，既有supabase-auth停用不启动、不接管不相关账号。当前进程/已知plist/.env只查OIDC五项是否非空，不输出值或读取秘密存储。

通过有限LOGIN固定目标预检，READ ONLY与原TenantScope核成员角色计数、dev与非dev主体计数和摘要；缺表/权限拒绝保留原错误，不提权绕过。独立新连接重复聚合证明一致，Source/Registry写为零。若真实publisher/OIDC仍不能确认，准确登记缺失入口，不发新token、换actor、伪造Root或强开Host。整Task仍未完成。
