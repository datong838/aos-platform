# 电商首装九路由登记设计 v2

2026-09-13；基线97e09d5f。按用户持续开发及真实栖月汇验证授权开展产品实现，m1串行，不push，230 L0及外部发布不在范围。

## 当前事实与原设计遗漏

05:18权威库当前九路由、业务ScheduleBinding、Occurrence均0。CanonicalRouter严格拒绝未登记路由；Cutover.prepare_activation要求已存在完整九项legacy/fence=false路由。PG测试由fixture预置这九行，因此不能证明真实首次安装入口完整。

05:20只读ACL复查：独立非superuser/bypassrls的runtime登录采用aos_runtime后，对dispatch绑定实际有SELECT/INSERT/UPDATE/DELETE；maintainer仅SELECT。实际ACL与ar2_001所定义runtime只读不同。恢复库宽权限来源仍需单独追溯，不据此直接INSERT，也不声称角色收敛完成。证据dispatch-entry-current-observation-v1.json及dispatch-entry-role-acl-v1.json。

## 产品行为

安装完成配置后，用户在正式安装控制入口登记已验证包声明的九项经营路由；一次原子登记，全部默认不可执行。登记仅创建固定元数据与不可变Receipt，不运行Case/Run，不读取商城或调用模型。重复同一请求返回原Receipt；同键异载荷、已有组、部分组、跨租户、安装/配置漂移均拒绝。

登记后用户可以审阅exact登记Receipt与固定九项操作，再由既有切换审批体系激活。首次未激活登记也必须能安全卸载/替换；不能要求不存在的切换Receipt才能清理未启用登记。

## 实现清单与依赖

1. 新增登记契约与预览服务：固定操作集合来自ECOMMERCE_GROWTH_OPERATIONS，不接受调用方自选handler/SQL。输入installation ref、generation、binding revision、execution epoch、config ref、idempotency key，当前persisted角色与markings核验；预览不是授权。
2. 独立迁移新增append-only登记Receipt，记录tenant、安装/配置/lock摘要、组ID、九路由snapshot、actor、requestHash和时间；RLS、不可变触发器、唯一tenant/idempotency。精确登记函数只创建完整默认fenced组及Receipt，专用maintainer执行，无任意表写权限。新访问能力需完成针对性权限评审与隔离PG负例后才正式部署，不借用当前runtime宽权限、超级用户或fixture执行真实登记。
3. Cutover.prepare_activation增加“真实首次登记”来源：只接受登记Receipt证明的完整legacy/fence=true组；既有legacy/fence=false路径保持原样。禁止泛化为任意fenced组可切换。prepare/commit/rollback/replay均保留exact snapshot及审批核验；回滚恢复原fenced状态。
4. 正式安装控制API接入登记Owner，依赖身份/安装/配置现状，无直接数据库后台脚本替代。固定九路由的角色与markings检查复用安装控制权限服务。
5. 未激活登记在禁用/卸载/替换时以专用不可变撤销Receipt释放或转移占位，禁止无痕删除、禁止在新generation继承旧执行权。已激活路径仍由现有cutover/lifecycle所有者处理。
6. 完成当前主库权限差异清单及代码迁移定义对照，确保部署不依赖宽权限。回退不删除历史Receipt或降级RLS。

## 最低测试门

拟修改文件（逐项施工前再核对所有权与现状）：
- services/aos-api/aos_api/ecommerce_growth_registration_contracts.py：严格请求/只读预览/Receipt契约；不接数据库或授权。
- services/aos-api/aos_api/ecommerce_growth_registration.py：正式登记Owner，复用当前安装与配置读取、角色/markings校验。
- services/aos-api/alembic/versions/a0v_026_dispatch_registration_receipt.py：首先建立不可变登记Receipt，仅runtime读取，无任何写入/函数执行授权；后续独立迁移提供经评审的受限登记入口与撤销Receipt。仅完成隔离验证后再决定部署。
- services/aos-api/aos_api/ecommerce_growth_cutover.py：仅支持带真实首次登记Receipt的fenced起点，保留旧路径。
- services/aos-api/aos_api/routers/bundle_runtime_installations.py：正式安装控制登记/预览入口。
- services/aos-api/tests/extension_runtime/test_ecommerce_growth_registration_contracts.py、test_ecommerce_growth_first_registration_pg.py：新增契约和实际隔离数据库验收；旧cutover/lifecycle/OCI测试继续保留。

迁移文件名为设计预留，实施时仍需核对最新迁移head，不能因预留号覆盖既有文件。独立的权限评审结果与真实部署结果必须分开记录。

### 首个代码切片：请求与预览

Request复用CurrentInstallationRef、ConfigurationRef；generation、groupId为严格规范UUID字符串；bindingRevision、executionEpoch为正的严格bigint；幂等键复用安装控制校验。extra forbid，不接受operationIds、handlerKind、actor、SQL、credentials等任意注入字段。固定schemaVersion区分未来版本。

preview只输出请求hash、exact安装/配置引用及九项legacy/fence=true/revision1的拟登记snapshot，明确executable=false、authorityValidated=false；组内installation/generation/epoch保持null，真正目标仅在请求中记录，不能绕过切换。输出是分离字典，修改预览不会改变请求或后续hash。验证未知字段、UUID/数值拒绝、同请求hash稳定及任一exact字段变化hash变化；不声称本切片完成登记持久化。

- 无既有路由→一次完整九路由fenced登记，CanonicalRouter仍拒绝；同请求重放无重复。
- 双写者同scope、不同组ID竞争只允许一个完整组；任意已有部分组拒绝且不补齐。
- 跨租户、错店铺配置/安装版本/lock/generation/epoch、无当前角色/markings、未知操作及普通runtime/Web身份均拒绝登记。
- 中途失败整事务回滚；Receipt不可更新删除；禁止普通身份直接改dispatch。
- 首次fenced登记的exact审批切换、配置漂移、过期撤销审批、commit崩溃重放、rollback恢复fenced；旧legacy路径回归。
- 未激活登记可禁用卸载重装，已激活须先fence/drain/detach，不能绕过旧generation任务排空。

## 经营首链接续

### 回执存储切片

本波新增a0v_026_dispatch_registration_receipt.py及tests/extension_runtime/test_dispatch_registration_receipt_pg.py。登记回执绑定tenant、安装/generation、group、requestHash、canonical payload与contentHash；tenant/idempotencyKey及tenant/group唯一，外键指向原runtime binding。复用canonical_asset_registry_jsonb与pgcrypto校验内容摘要，普通runtime只有SELECT，PUBLIC及runtime无INSERT/UPDATE/DELETE/TRUNCATE；所有身份的更新/删除/截断由不可变触发器拒绝。无新增可执行高权限函数，无九路由写入。payload的具体九项及当前权限由后续正式登记Owner/受限入口验证，此表不是独立写入API。

用18432独立测试数据库（沿用description PG fixture）验证真实迁移、哈希漂移拒绝、不可变历史、唯一组/幂等键、runtime不可写和跨租户不可见；测试Owner种入回执仅验证存储，不称真实登记成功。主库本波不迁移、不授权。

### 原子登记入口切片（隔离实现，尚不部署）

新增alembic/versions/a0v_027_dispatch_first_registration.py及tests/extension_runtime/test_dispatch_first_registration_atomic_pg.py。提供固定签名JSON请求+actor的受限登记函数；仅非superuser、非bypassrls的专用maintainer登录在serializable事务并采用maintainer角色时可调用，runtime与PUBLIC无EXECUTE。函数不接受调用者的操作集合、handler/fence或SQL。

在同事务内按tenant锁定登记命名空间，核对persisted安装角色/markings、安装active/etag/lock/overlay、唯一当前generation/epoch/binding/configRef及不可变配置来源行，再登记固定九项legacy/fenced路由及a0v_026回执。请求hash由既有canonical JSON函数生成；payload绑定actor，重放须同key同请求同actor；不同请求/已有组/部分组拒绝，不补齐。普通runtime不获得dispatch表INSERT权限。

安全边界：maintainer是受信任的控制服务身份，不对浏览器或业务模型开放；正式Owner必须先运行既有四来源配置预检并保留锁，函数本身仅复核存储目标与安装角色/markings，不把元数据登记当业务执行权。完整四来源与签名声明的正式Owner接线、首次fenced切换和未激活撤销未完成前不部署或真实调用。该函数增加受限访问范围，权限评审须与隔离测试结果一起审阅，不因代码完成自动授予主库权限。

### Owner事务衔接切片

新增ecommerce_growth_registration.py及ecommerce_growth_registration_receipt.py；修改registration_preflight.py提取当前安装/四来源核验，不含空组判断的内部复用函数，原registration_preflight行为保持不变。正式register仍强制执行当前核验，随后只调用固定027函数（该函数核对空组或幂等重放），不通过参数跳过权限。使用既有consumer_connection，专用空闲连接在事务建立前指定serializable；预检采用runtime，调用固定函数时临时采用maintainer，读回后回到runtime，同连接同事务验证存储Receipt的hash、scope、request、actor及固定fenced snapshot后才提交。未知失败不自动重发。

历史读取独立于register：读取并核验不可变Receipt后，按该安装当前persisted角色与markings校验，只返回历史证据，不打开路由或恢复代次。目标已变化时register仍拒绝，历史读取不依赖旧的空组/epoch。API接入和签名声明资格仍留后续，不能把service注册成功视为完整安装链完成。

测试文件test_ecommerce_growth_registration_owner_pg.py与test_ecommerce_growth_registration_receipt.py。隔离PG中实际使用027、真实非特权双角色连接和RLS；为观察事务编排可替换当前权限检查节点，必须明确这部分是编排测试，不能声称替代真实四来源验收。覆盖检查先于写入、同连接事务、拒绝时无写、重放、回读异常回滚及伪造Receipt拒绝；当前预检46项已有测试继续回归。

### 当前安装登记前检查切片

新增services/aos-api/aos_api/ecommerce_growth_registration_preflight.py与services/aos-api/tests/extension_runtime/test_ecommerce_growth_registration_preflight.py。复用PostgresInstallationStore和CurrentFourSourceConfigurationAuthorization，不接受假权限callback或调用方路由列表。先锁安装CAS，再读取active lock，检查resolved内solution.ecommerce.growth唯一存在；精确锁定runtime generation/bindingRevision/epoch/configRef并要求enabled/ready/unfenced。调用既有read_configuration完成当前角色、markings及四来源核验。当前tenant存在任一九项路由就标记不满足首次登记条件，不能预览为可补齐。

输出只包含安全引用、checkedAt、固定fenced预览及currentConfigurationValidated；authorityValidated仍false，businessWrites=0。函数只在调用方已有受控事务中读与锁，无INSERT/UPDATE/DELETE，没有新授权。执行登记时必须在同事务重用检查，不能把预检结果作为未来写入授权。测试覆盖runtime字段漂移/类型伪装/配置变更/组已存在/权威依赖拒绝；随后以当前真实安装只读核验。检查不证明签名包声明已具备完整登记资格，该资格在正式Owner写入前另校验。

登记与激活完成后接源事件消费者：SourceSelection/current配置校验→按事件存在性扫描而非MAX revision→冻结deadline→record_event_batch→CanonicalRouter→initial_store_analysis。下架/删除事件要撤销旧候选，候选状态函数不能过滤事件流。需要新版本平台包纳入候选状态规则；当前签名1.5不改动。真实成功门是Case/Run和后续业务产物，而不是九行登记或测试通过。

### 当前签名声明资格切片

新增 services/aos-api/aos_api/ecommerce_growth_registration_qualification.py 与 tests/extension_runtime/test_ecommerce_growth_registration_qualification.py。复用 RuntimeReleaseRevalidator 在调用方已有事务内的 Registry 锁、当前信任根与发布证据检查，禁止另开连接形成签名检查时间窗。锁内必须唯一选择经营 SolutionPack；固定九个 POST/exclusive 的 operationId/path 必须完整、无重复、无额外 API。其完整 contributions 摘要须匹配重新验证签名清单得到的 backend_claims，不能凭安装锁里同名包或伪造声明放行。返回安全资格摘要，不授予执行权。非 API 声明一并绑定摘要但不新增前端能力假设。

本切片先独立测试并用当前真实安装执行只读资格检查；随后 Owner 必须在同一登记事务接入它，正式 API 仍需完成连接配置、权限评审、fenced 切换和未激活撤销。此切片不迁移主库、不调用登记函数。测试含缺失/重复/替换接口、错误方法路径、不同包类别、无 backend、签名摘要不符和当前发布检查拒绝。未修改任何已签名候选包。

真实只读检查发现安装锁会重排 contributions：23 项与签名 manifest 集合一致、顺序不同。不能用原始列表摘要作语义等价判断。补充修改 extension_runtime/registration.py，基于既有 _index（拒绝重复 conflict key）生成顺序无关摘要；release_revalidation.py 的 RuntimeReleaseCheck 追加 backend_claim_fingerprints，保留既有 backend_claims 原值与消费者行为。登记资格只比较新语义摘要；发布签名本身仍按原始 descriptor 完整核验，不放松密码学验证。测试补充重排一致与重复声明拒绝。

### Owner 强制签名资格接入

修改 services/aos-api/aos_api/ecommerce_growth_registration.py 与 tests/extension_runtime/test_ecommerce_growth_registration_owner_pg.py。构造 Owner 必须提供 exact ReleasePolicy，不给默认绕过；当前安装/四来源检查后，在同一连接和 serializable 事务重新取已锁定安装 baseline，执行 qualify_registration_release 后才切换 maintainer 并调用 027。资格结果须锁摘要一致、固定 schema/包ID/九项、executable=false；缺失、失效、异常结果一律零写回滚。历史读取仍只做当前访问权限检查，不重新授予资格。隔离 PG 编排测试替换资格节点并核对与实际写回执相同 backend pid/tx，另测拒绝无写；真实签名验证沿用上一波当前主库只读证据，不以编排替身冒充全依赖正式 API 验收。

### 正式 HTTP 适配与安装上下文历史查询

修改 aos_api/routers/bundle_runtime_installations.py，新增 POST /v1/bundle-runtime-installations/{installation_id}/ecommerce-growth-registrations 和 GET 同路径 /receipt。POST 要求严格既有 FirstDispatchRegistrationRequest、单一 Idempotency-Key/If-Match 且与正文完全一致；actor/tenant 仅来自 Principal，路径安装必须与正文一致。GET 用单一 Idempotency-Key 查询指定安装下回执，强制调用当前权限 Owner，无重新登记。首次返回 201，幂等重放 200；不自动重试。

修改 aos_api/ecommerce_growth_registration.py：历史读取必需 installation_id，_read SQL 加安装过滤，既有 register 回读同样绑定请求安装；不能把另一安装的同键回执当目标返回。无权、未找到、漂移和数据库错误使用固定安全错误文本，不泄露原始 SQL/连接信息。未知提交结果用独立历史查询核验。

修改 aos_api/asset_registry/control_wiring.py：RuntimeControlPlane 追加可选 first_dispatch_registration_service；build_runtime_control_plane 仅在宿主显式传入 registration_connect 时构造，默认 None，不回退普通 runtime/Web/超管连接。构造不连接、不迁移、不启动任务；缺少正式服务 HTTP 返回503。维护身份安全文件读取、角色权限部署及启动集成后续独立审查，不能把接口测试当已对主库开放。

测试新增 tests/extension_runtime/test_ecommerce_growth_registration_http.py，更新 Owner PG 测试和 control wiring 测试。覆盖 Principal 绑定、路径/版本/键不一致、未知注入字段、重复/缺失头、回执查询、未配置服务、固定安全错误、只调用一次、错误安装历史不可见；既有安装操作 API 回归。主库不进行登记/迁移/身份授权。

HTTP RED 发现两项需修复：通用 FastAPI 校验错误回显 unknown input，且请求契约顶层导入 Host 操作集合使原惰性控制平面提前加载安装服务。仅给新增登记子路由使用 APIRoute 校验异常转换，返回固定422文案而不更改全站错误行为；将请求契约中仅 preview 使用的操作集合延迟到函数内导入。追加修改 ecommerce_growth_registration_contracts.py，保留模型、hash、预览结果不变，并回归既有惰性导入测试。

惰性导入基线复核更正：把本波修改模块替换为 0e26444b 原始源码的独立进程仍提前加载 installation_store/revalidation。实际链为既有 routers/pipeline_controls.py 顶层导入 pipeline_runtime_control_owner._ref_identity（提交11628a93），并非全部由新登记契约引入。本波增加最小修复：将该单一 helper 导入移至 ScheduleBindingRequest.exact_binding 内，校验执行不变，补跑既有流水线 HTTP 测试；不改流水线业务状态或数据库。前述把惰性失败全归因新请求契约的初判撤回。

进一步追踪确认同一既有流水线路由还通过 _text 顶层导入另一 Owner。两个 helper 均延迟至实际使用点（exact_binding 与 _approve）后，原惰性导入测试通过。没有删改校验；既有流水线审批与调度绑定 HTTP 一起回归。

### 专用登记连接与启动组装

新增 aos_api/ecommerce_growth_registration_connection.py 和 tests/extension_runtime/test_ecommerce_growth_registration_connection.py；修改 main.py 的控制平面构造注入 selector 返回值，并回归 runtime_startup_composition。只读环境项 AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE，内容采用固定 schemaVersion/role/dsn，绝对路径、当前UID、普通文件0600、拒绝符号链接、限制64KiB；无环境DSN/Web/runtime身份回退。不记录或返回原始文件、DSN、连接异常。

连接建立后先在独立短事务核验：session_user/current_user 等于文件声明的独立登录名，登录非super/bypass/createrole/createdb/replication、NOINHERIT；可达角色仅 aos_runtime 与 aos_extension_maintainer，禁止多余继承链、缺角色或admin_option。两组角色须非登录、非super/bypass/createrole/createdb/replication。检查结束恢复IDLE后才交给已有Owner；每次连接重新验证，无权限授予/迁移。默认selector返回None，显式配置才提供固定连接函数，启动只组装不执行登记。

测试安全文件坏权限/相对路径/符号链接/错误结构/未知字段无连接，异常不回显；隔离PG真实非特权双角色连接通过，超管、单角色、额外角色/管理权限拒绝，交付IDLE；已有启动/HTTP/Owner回归。正式主库身份创建和026/027迁移需随后依据权限审查与完整验收部署，本切片不改主库身份。

### 登记前权限审查与受限行锁缺口

08:03主库只读目录审查：dispatchRows=0；aos_runtime仍有dispatch表SELECT/INSERT/UPDATE/DELETE；aos_app为superuser/bypassrls且拥有表；列级ACL为空；026表及027函数未部署。新身份连接的角色图检查不能解决表默认授权与原Web超级用户问题。

早期228ti2e6rls的ALTER DEFAULT PRIVILEGES授予未来表runtime DML；ar2_001只REVOKE PUBLIC再GRANT runtime SELECT，没有撤销runtime已继承的默认DML。需结合本次pg_default_acl证据和隔离重演判断机制，不能把历史实际执行归因写成已查明日志事实。

此外ecommerce_growth_host_ports.py在锁定dispatch组时直接SELECT FOR UPDATE，只有SELECT权限会失败；旧test_ecommerce_growth_host_ports_pg.py为自定义Host测试角色额外GRANT SELECT,UPDATE。因此禁止只做REVOKE就部署。先设计并实现固定租户/组的受限行锁读函数（不改dispatch数据、无任意SQL/表名），Host通过其持有同事务行锁，再精确撤销dispatch表普通角色DML。签名/审批/Receipt/隔离检查仍保留。runtime binding也存在FOR UPDATE依赖，必须列入权限矩阵，不能宣称整个运行控制表都只读化。

本波新增tests/extension_runtime/test_dispatch_default_privileges_pg.py，用18432独立测试库复现历史DDL在默认DML存在时仍留下写权限，以及撤权后普通SELECT成功而直接FOR UPDATE失败；这是缺陷证据测试，不是权限修复GREEN。下一实施切片预留a0v_028（须重新核对head），新增受限行锁与权限收敛迁移，修改Host与真实非特权并发测试；全部通过前不应用主库ACL变更。

### 受限路由组行锁迁移切片

新增 alembic/versions/a0v_028_dispatch_read_lock.py 与 tests/extension_runtime/test_dispatch_read_lock_pg.py。固定public.extension_dispatch_lock_group_a0v_028(uuid)，返回既有Host所需九字段；只允许非super/bypass session采用aos_runtime、serializable且scope GUC非空，锁定本租户本组全部记录（上限10，必须恰好九个已知经营操作），以原排序FOR UPDATE持锁，不修改数据。错误/部分/额外组拒绝；函数不是执行授权，Host仍需逐项exact/fence/runtime/权限复核。

同迁移对dispatch表PUBLIC/runtime/maintainer撤表级与列级直接权限，恢复runtime/maintainer SELECT；新函数PUBLIC/maintainer无EXEC，仅runtime。原受限027登记和既有切换函数仍作为写者；其他表和全schema默认ACL不变。历史迁移不编辑。

隔离PG复现带默认DML的历史状态，执行新迁移后普通runtime INSERT/UPDATE/DELETE/TRUNCATE和列级UPDATE均失败，固定027仍能登记，合法加锁读取九项、canary/错组/部分组/非serializable/超管拒绝；双连接更新须被行锁阻塞，事务结束释放。此切片不切换Host生产读取、不部署主库，Host接入与回归完成前禁止部署，避免撤权造成现有直接FOR UPDATE失败。


### Host 受限锁与专用 runtime 连接接入
修改 services/aos-api/aos_api/ecommerce_growth_host_ports.py，将路由组直接 FOR UPDATE 替换为固定 public.extension_dispatch_lock_group_a0v_028(uuid)，保留 exact、fence、runtime binding 行锁、权限与 Receipt 同事务校验。新增 aos_api/ecommerce_growth_runtime_connection.py，复用 runtime_worker_connection，要求空闲非 autocommit 连接、exact TenantScope，设置事务隔离与作用域，复用 require_runtime_role 验证非特权、非表拥有者和 FORCE RLS；读引用使用只读 REPEATABLE READ，Host 使用 SERIALIZABLE。不包显式 transaction()，保留 Host 最后显式 commit 的语义。CanonicalRouter 与 LockedHost 默认使用此连接，不回退 Web。
测试修改 tests/extension_runtime/test_ecommerce_growth_host_ports.py 和 test_ecommerce_growth_host_ports_pg.py：后者升级为独立数据库 public 表、真实非特权 LOGIN+aos_runtime、九项完整组和028迁移，测试生产连接路径、Receipt 回滚、权限拒绝和隔离；新增连接只读/提交/超级用户拒绝验证。先 RED 再实现再联合回归。主库不部署、不登记、不激活；回滚为代码回退，028仍未上主库。

兼容回归补充：test_ecommerce_growth_canonical_router.py 更新 SQL 替身匹配；旧 test_ecommerce_growth_signed_lifecycle_pg.py 私有 schema fixture 增加028迁移，并仅对该历史测试的固定函数名映射 schema，使用真实非特权角色调用。它不是 public 部署证明；public 原始迁移/生产连接证明由本波独立数据库 Host 测试提供。


### 首次激活登记来源核验切片
新增 services/aos-api/aos_api/ecommerce_growth_registration_origin.py 与 tests/extension_runtime/test_ecommerce_growth_registration_origin.py。严格不可变 RegistrationReceiptRef 固定资源类型、canonical UUID、revision=1、sha256；verify_registration_origin 复用既有存储回执解码，绑定ref id/hash、scope、当前按operationId排序的完整九项快照、目标安装/generation/epoch/bindingRevision；严格拒绝bool伪整数、假对象、partial/mixed/revision漂移。返回重新验证且独立的原始登记请求，供后续同事务当前安装/配置/签名核验复用，不直接授予激活权。
本波不放宽Cutover判断，不部署主库。后续接入需要：审批payload精确绑定registrationReceiptRef；旧请求无该字段时序列化/摘要必须保持原字节语义；prepare Receipt与重构请求保留新ref；prepare/commit/rollback分别复核来源和当前配置，rollback恢复旧snapshot的fence=true。撤销并发须与group/installation锁序一致，不能删除登记历史。现有SQL commit/rollback按exact snapshot比对/恢复，无需凭名称猜测放宽数据库检查。
