# BudgetPolicy 续期 B：保护身份配置、私有连接与单次 IPC 完整方案

## 1. Rules 与基线

用户 AGENTS、AOS 工程交付、231 完整长程 Goal、原 ABC 总方案。唯一 m1 writer codex-01a13484-f019-7d82-94ce-812396db9124。Authority AOS-002026，m1 c5c06bd8110d611f30fb7a643160bcc4f76d6182，完整 A 已准确候选 Delivery/释放 Lease。四全量分包与综合独立 PASS 均已合法消费，211 native/相邻 cases；只读 genuine 原 OIDC 身份验证不是预算批准。

本 B 是原总方案的完整七文件实施，不缩为配置解析或 mock 交付。只有原真实 org-org/dev-project 与唯一真人 subject6f31cfdc-a26c-4f1f-ad6b-95a8559cc657。原 DB schema161/650表只读，原 Policy13 过期且未续期，Budget1 到2027；Host/worker/Provider OFF。原命名卷/原安装批准/旧12未知 Run/disabled Schedule 不改，不源码接入商城源，不 push/发布。每天/每次 aos 原卷最新 m1 PG→API→Web 完整重启及八台原稿视觉/真实经营首链仍分别待验；匿名 Goal continuation 不是 aos 提醒。

本 Task 范围已由受支持入口登记，Lease到2026-10-14T04:00Z；父维护 Lease仍到00:00Z，不能凭TTL抢旧Owner。编码前独立文件级方案复审，保留所有过去开发及 userdirty。此次不开放原 Role，不部署原迁移，不新增 API/Web 路由。

时序声明：总方案原2026-10-13页首“当前仅方案/先登记A”的语句是当时历史阶段，已被A正式Delivery与本Bregistration推进。此次审阅是**B编码之前的前瞻方案路由评审**，不是B实施/交付声明；七源文件尚不存在正是用户“先方案、再编码”的要求。A已完成且精确提交，不能因历史方案正文退回重登记/重做A。planr2把待编码方案当缺已实现代码返回REWORK，原result合法消费保留；新材料须同时给A Delivery、B registration、当前HEAD与候选源码SHA作为时序依据，仍不把B声明为完成或已就绪运行。

## 2. 精确文件目录与职责

1. `services/aos-api/aos_api/aip_budget_policy_renewal_connection.py`：严格保护配置/原本机 OIDC loader 复用适配、私有目的连接、可信来源 pin、启动 native source/角色/函数/ACL/schema seals 检查。
2. `services/aos-api/aos_api/aip_budget_policy_renewal_service.py`：唯一操作分发，复用 A Store/严格 command；decide/revoke 每次原 resolver，机器与 consumer 不接受 Principal 替身。
3. `services/aos-api/aos_api/aip_budget_policy_renewal_process.py`：一进程一请求 stdin、bounded JSON、durable Attempt 先于写、strict stdout、失联/unknown 只读对账；不自动重试。
4. `services/aos-api/aos_api/aip_budget_policy_renewal_schema.json`：精确 IPC request/result 结构，已知 operation 和 command 对应，extra properties 关闭；无 actor/身份配置/连接字符串在公共请求。
5. `services/aos-api/tests/aip/test_budget_policy_renewal_connection.py`：保护文件/实际目的角色/来源漂移/原配置与 FakePrincipal 负例。
6. `services/aos-api/tests/aip/test_budget_policy_renewal_service.py`：全五操作、原 canonical/ref/hash、原人与机器分离、当前态/撤销/副作用否定与隔离 native 非空链。
7. `services/aos-api/tests/aip/test_budget_policy_renewal_process.py`：真实子进程、断链/超时/部分协议/Attempt保守恢复/伪造stdout/精确readonly history。

只新增七文件及本 evidence/D-wave。A 八源码和原 generic auth/原 budgetcost/process、用户 dirty aip_action/cost_runtime/reservation/modelEval/capacity 全排除。发现必须跨文件时先调整 Scope/方案，不能暗改。前端、正式私有身份登记及真实部署属于 C/独立授权门。

## 3. 保护配置与真实连接

内部配置必须来自可信绝对路径文件，不从请求、共享 API DSN、AOS_DATABASE_URL 或 connect_factory fallback。固定 tenant/三种 purpose 到 A 精确 caller 名，固定唯一 checker 与原 management OIDC 配置；复用已审原 load_management_oidc_config 的路径/权限/loopback 合同，先查其所在模块及 imports，不加载会执行维护的脚本。

私有目录0700/文件0600、当前用户owner、拒绝symlink/非正规文件/宽权、限制长度，保护文件读取/校验摘要与当前 provenance。路径/配置/身份不一致→unavailable，不能改文件或放权自修。启动核原 subject、issuer/audience/JWKS/token URL/RS256/externalOnly/devOFF/leeway原值及配置 SHA；禁止客户端提交 CheckerBinding、JWT环境或任意JWT issuer；检查危险代理/重定向相关环境对原只读 resolver 的影响，不能把原 external-only budget/issuer auth 普遍放宽。

已核原loader位于 `/Users/ddt/work/projects/ai_agent/aos-platform/scripts/a0v_qyh_restored_http.py:load_management_oidc_config`，其唯一本机导入 `a0v_current_preview_http` 顶层为常量/import/function定义，维护启动在__main__内，不能调用main/prepare/serve。B仅从当前可信冻结包路径导入并核两个脚本源hash，调用原纯loader；不复制其验证逻辑、不从公网/请求选择模块。预计内部接口：load_protected_config(path)→不可变ProtectedRenewalConfig；open_purpose_connection(config,purpose,read_only)→独占真实Connection；RenewalService.execute(request)/reconcile(request)；process解析和调度固定上述入口。

私有配置严格schemaVersion/固定tenant/enabled默认false/identityConfigPath+SHA/三个purpose profile/可信部署包源hash，profile含host/port/dbname/精确user/passfile路径及expectedNativeManifestSHA；禁password字段、任意sql、连接URL的附加options、未知key和public配置参数。各配置/原oidc/passfile/可信来源文件分别安全open与稳定stat/hash核对，native原库身份和manifest必须与可信配置预期一致；fixture/prod不可凭公共请求选择。正式enabled值及真实来源只在C批准后部署，B仅独立fixture。

每目的使用专用私有 passfile/严格DSN字段，禁止密码复制到日志、CLI或环境；核 host/port/dbname、真实 `.info.user`/session_user/current_user、租户 GUC、READ COMMITTED、schema/role flags/无membership/manifest/table ACL。真实 psycopg.Connection 必须独占、IDLE、非autocommit；不可共享通用 API connection。默认 config closed；无配置、原schema161、roleNOLOGIN或来源未正式登记都真实 closed，不执行DDL、启用Role、签署批准或变更原卷。正式本机环境的实际部署来源/Role凭据放行在 C 的具体可审查步骤中完成。

B 在隔离 native 环境验证保护 loader 与连接完整性；不把 A 的 CheckerBinding 字段形状当已部署私有配置来源。schema管理员同时修改 body+seal 为明确TCB compromise；新 service 的保护部署源摘要检查须与可信本地包匹配，不自证被修改函数。

## 4. 服务与 IPC

propose 仅机器实际 PG session；decide/revoke 仅原 pinned issuer purpose 且 SecretStr JWT 在原 verifier/current-member 查询后执行；consume 不接受人类 actor 参数或任意 SQL，仅持久化 exact approval 的 A consumer；reconcile 强制 READONLY 原 request/key/hash/ref，不重造提案、不换key，不把 unresolved 当无写入。

一进程从stdin读取一个有长度上限的UTF8 JSON对象，拒绝多对象、重复key、NaN/Infinity、bool/int混淆、未知op/未知key/任意actor/任意purpose/SQL。operation由严格类型映射专用连接；tenant固定；仅issuer写请求可携JWT，SecretStr在内存，所有 stdout/Attempt/日志/异常不带token。requestHash复用 A domains，不将JWT或配置写入hash/Receipt。

写入之前 fsync durable Attempt 到可信0700/0600目录，namespace是本新B，不借旧Attempt记录。记录 op、固定scope、原 canonical command/key/hash/ref、nonce与状态，不含凭据。exclusive creation/同key冲突检查、目录fsync；existing attempted/unknown 禁止execute，只有原请求readonly inquiry。attempt落盘失败/部分文件/不可解析→拒绝写，不修文件后重试未知动作。observed仅在 A Store 外层COMMIT及strict returned DTO通过后记录；consumer/issuer结果不能由stdout或页面标签自行认定。

child exec参数只含固定模块/可信配置与Attempt路径，不放JWT/密码；shell=False，stdin携唯一请求；父级deadline、bounded输出、真实句柄终态，观察timeout不是进程终止。无效stdout/连接/提交回执未知标unknown，先独立只读；禁止自动杀后重发、补key、生成新proposal。已知SQL拒绝且确认rollback可记录blocked，但仍不自动重复。结果fixed schema/op/hash/metadata/activationEligible=false；stderr只安全稳定code；C展示待批准/unknown/closed，不以准备成功当执行许可。

## 5. 真隔离正例与测试路径

纯合同/config负例先RED，然后最小完整实现。真实隔离非空链必须经**密码或同等真实DB登录 + genuinely signed isolated JWT verifier + native current-member/Store**，再propose→decide→consume→reconcile/currentread；拒绝/撤销、currentBudget/Provider/head/member变化、跨tenant/role伪装、配置/包漂移、expiredJWT/错误iss/aud、部分Attempt、unknownack、进程格式攻击均无半状态/无自动重放。原 generic external-only auth tests原样验证，真实原OIDC只读认证正例保留，不能用真实用户JWT代签任何fixture预算。

隔离认证正例主路径：已缓存 `aos-current157-frozen-tool:20261008-r3` 镜像sha982fd540...只作Python依赖运行时，显式python entrypoint，不执行其旧代码。只读挂载本次精确冻结代码，PG新owned tmpfs，worker共享该测试PG网络namespace；**自己的loopback18448**上运行isolated JWT/JWKS issuer，URI合同与 A pin一致但属于独立namespace，绝不碰真实18448的Keycloak。固定fixture subject与scope、测试前置member明确标fixture；没有原真人token/密码/真实Budget同意。真实签名校验/HTTP/JWKS/PG仍完整，不 monkeypatch Principal/resolver成功。使用当前缓存镜像，不 pull；先只读核依赖/入口/冻结来源。首次依赖探针缺jsonschema，不算已就绪；schema可由严格Pydantic与静态JSON合同校验方式决定，若真正需要运行依赖先找现有缓存，不装到真实服务。

当前真正的运行导入物证：Colima看不到该host bind目录，r1只读容器也拒绝docker cp，均已终态对账且无源码执行；r2在owned测试层初始化公开冻结源码，tar回读核A八文件SHA，运行UID65534/无network，实际A Store与原JWT verifier导入PASS、stdout固定成功、无stderr、无私有文件复制。服务运行不用缺失httpx/jsonschema：原OIDC使用urllib；IPC以严格Pydantic解析/校验，schema.json由同模型生成并以canonical生成schema等价自测（不能只测文件存在）。Linux进程fixture仅按这条已验证依赖路径，公开源码初始化后权限只读/非root执行；真正PG+JWKS联合namespace和完整非空链仍是B出口未完成证据，不伪称ready。

只操作精确own CID/labels/tmpfs/no原卷，无未知启动脚本，无批停/prune。原卷未读取商城源/未迁移/无预算写；fixture terminal按同handle/库只读回读再停止。断链/到期以真实DB时钟和真实进程/锁同步，不靠盲sleep或增加产品超时掩盖缺陷。

## 6. 退出与下一步

完整七文件实现、专项/相邻+真实隔离端到端/进程与配置来源矩阵、自洽/风险、冻结独立code/native复审PASS合法消费后才Delivery/精确m1/Authority+Prime **强投影**。禁止使用统一sync生成个人Codex记忆；A误生成的当前note已精确撤回，个人note保持eventualSTALE。

B不是用户真实预算批准或原部署；C待审完整proposal、具体窗口/原额度/原scope/targethash/唯一用户最后批准动作，当前原则下须有真实部署放行才开启原有界写入。原Price/model依赖不因policy续期自动就绪。真实 sourceSelection/runtimeControl/新自然触发/CaseRun/内容评审续跑/Wiki/八台真实与视觉/生命周期/观察发布完整长期目标持续保留，下一已登记安全波不因局部门限停工。

## 7. 2026-10-14 接续检查与增补验证

上一轮40项纯边界测试终态已回读通过。当前继续原七文件范围，不交付部分实现。补充保护路径祖先symlink/路径别名拒绝：只有规范绝对路径可读取，避免合法末级0700目录掩盖上层别名。对已有连接代码只整理缩进，保持操作异常不被setup异常包装；read_only和confirmed blocked最新更改重新验证。B service测试复用A只读测试fixture定义，在新隔离库验证实际protected目的连接、机器proposal、durable marker、同key重复只能reconcile及精确历史；不以该机器正例代替后续真正签名issuer完整链。原A测试/源码不修改，原人JWT不用于预算操作。

隔离 full-schema 正例的历史前置数据新增明确约束：原 A 小schema测试的直接ACTIVE fixture INSERT在完整162库被原Budget消费guard正确拒绝（r3，P/D/政策均0，setup事务回滚），不是B失败后重放。B独立fixture仅在admin事务/DDL锁内暂时停用两个精确历史INSERT guard建立fixture Budget1/旧Policy13，**同事务恢复guard再提交**；无B操作可在停用态运行。原函数body/owner/ACL不改，current-member仅fixture，后续B真实私有角色/JWT/consume全走正常guard。新增验证记录guard恢复、SCRAM错误密码拒绝及原128 seal不漂移；不得将fixture前置历史称作真人批准。

## 8. 真实 IPC 协议 RED 与最小修复

r6/r7只读consumer子进程终态确认：退出0，stdout包含7条原loader导入产生的alembic JSON日志加1条正式结果，stderr0；父解析因此unknown。诊断重复的是明确reconcile读操作，不是execute重放。新增B process.py main中的输出通道隔离：读取/loader/service内部输出在redirect_stdout(sys.stderr)内，结果对象计算完毕后退出上下文，仅外部print一条协议结果。不修改原logging/auth/loader、不剥除日志后宽松解析，不因unknown调用写操作。以同原历史request/key/hash实际子进程与独立PG readonly回读复验，Receipt/Attempt计数保持不变。

r8证实单纯redirect不足：aos_api包的原logging_facade在模块main之前绑定了原sys.stdout，logger持有旧stream，故仍7+1输出。追加仅CLI main启动时把已有StreamHandler且stream恰为sys.stdout的handler转向sys.stderr，再用redirect隔离未来print/loader；不改共享logging_facade或全局API进程，原handler格式/级别保留。r8全是readonly，真实child退出0、无新Receipt，继续原历史只读复验。

## 9. 最新联合链与native防重故障矩阵

继续原七文件，当前先扩展 `services/aos-api/tests/aip/test_budget_policy_renewal_service.py`：在最新完整签名链中验证Partial Attempt保守unresolved/同key新hash conflict不写、真实PG COMMIT之后只在transport返回点注入RenewalStoreUnknown（原Store执行不mock，身份/JWKS不mock），B独立readonly回读且同marker重复不得再进入Store.propose。另验证保护config闭合及manifest comment漂移先于Attempt/写入、实际namespace loopback错误密码拒绝。每个负例恢复的仅测试fixture字节/metadata且不能授权未知execute；原COMMIT丢ack保留原command/key/hash。完整链保持单独正常四操作+实际childreadonly，额外lostackproposal只准备不消费，并准确更新计数/fixture物证。

r2 fresh full162 fixture用最新HEAD committed public source+B7 overlay，caller HBA全部IPv4 SCRAM以覆盖容器内loopback和host bridge，仍独立namespace18448测试JWT。old r1 PG/9 worker全部终态，不重启它们、不重用immutable journal库；原数据卷不接触。native联合链与矩阵完整通过前不能Prime code/native交付。

联合r10通过后，继续 `services/aos-api/tests/aip/test_budget_policy_renewal_process.py`：Popen transport故障点用真实无DB子进程输出匹配operation/hash的伪造observed，同时父进程必须在真实私有consumer READONLY session查询不存在的exact key而得到unresolved；不mock auth/Store.reconcile/PG。另实际子进程多JSON帧返回unknown，Receipt/Attempt不增加。该fault只用于明确mode=reconcile请求，绝无真实预算execute或未知重发。r11可复用r2已提交不可变历史做readonly验证，不重跑源fixture或四操作。

## 10. 四个写操作必须经真实子进程

r10已有service四操作+readonly真实child，但不能以readonly child代替IPC写路径。最新 `test_budget_policy_renewal_service.py` 正常四个操作统一经run_renewal_process实际module CLI、stdin原JWT仅内存、真实目的连接/Store/COMMIT、父独立READONLY；父返回observed是Receipt证据，不声称原子输出prepared等于运行激活。原service.execute用于同marker重复只读验证；lostack故障仍原Store真实COMMIT后模拟丢返回。r12另建fresh r3 tmpfs full162并跑最新七文件完整联合链（含forgedstdout），不重放r2已消费操作。复审须以此最新联合链/hash为准，不能直接用r10声明IPC写链已完成。

## 11. 自查补齐公开结果schema

首版质量p2实际PASS已在原七SHA当前时合法消费，p1两格式失败原raw不修。自查发现schema.json目前只有request合同而上位完整B要求request/result：不能以p2局部PASS或native成功掩盖该文档协议缺口。新增/修改仍仅 `services/aos-api/aos_api/aip_budget_policy_renewal_service.py` protocol_schema、`aip_budget_policy_renewal_schema.json`、`tests/aip/test_budget_policy_renewal_service.py`：在同文件$defs添加明确RenewalResponseFrame（5个顶层必填、extra禁止、version1/operation4/hash64/activationfalse；result的4个native元数据必填/status精确enum，原SQL产物字段允许并不做虚假完整typed声明）。这是child wire成功帧，parent internal process handle/unknown观察不冒充JSON成功帧。先RED证明缺定义，再生成与同函数等价并验证shape。旧p2覆盖保持历史合法、不是新SHA最终B PASS；新的freeze/hash/联合native及全量review须重新成立。

## 12. 复审格式问题：支持的SYSTEM入口补强，原validator不变

08机制§真实消费尺寸失败/前段SYSTEM逐字claim补强允许新的受限资料审阅，不改旧raw/不放宽validator/不重发未知请求。r4p2/p3均真实进程return0且rawJSONparse失败，已终态，不消费。新辅助文件仅本B evidence `review_full_b_system_contract.py`，不是修改原aos_review.py/Prime代码/全局配置。复用原validate_request/prepare_review_directory/prime_command/parse_response/validate_result/scan_secrets/consumption_record；仅在支持的Prime CLI --system-prompt参数末尾补完整身份/基线/claims输出框架并明确raw{...}首尾，框架证据/判定必须实际审阅、不能当PASS事实。原no-tools/无扩展/skills/context/session/模板/offline、retry/refine/compaction/telemetry禁用及bounded材料保持。新controller runnerSHA和原validatorSHA明确绑定，消费必须actual transport/严格rawJSON/同当前Baseline/自身SHA，不能伪称旧runner hash。每个新request独立one-shot marker与精确knownterminal；旧fence不剥除、旧结果不升级。该辅助只能B当前资料质量review，不授运营权。新的runner与结果一起作为B交付复核材料。

r5system p1/p2已严格PASS并合法消费，旧controller/sourceSHA保留。p3严格JSON PASS实际transport8753015字节超过原8MiB消费门（evidence2025/3208字符）；消费拒绝，不计该PASS最终门，不裁剪流/不扩大原上限/不复用原request。新增本evidence `review_full_b_system_contract_concise.py` 保留原helper，仅SYSTEM追加每finding evidence<=600字符和next_safe_step<=250字符、减少可重复长说明，完整材料/claims/独立质量判断及所有validator/flags不变。新request/自身runnerSHA/validatorSHA绑定与same-source baseline；这是新有限资料复审，无业务效果。成功后综合审阅同时审原/新controller，不伪称旧hash或跳过消费。

## 13. 9c96edf候选提交后的终验：机器Token字段Python别名

9c96edf3c4fe74f92708c7d30c485a29bdf42c96精确47文件已提交，B尚未官方Delivery/释放Lease/推进Authority。终验确认共享AipContractModel.populate_by_name允许bearer_token别名：consume带bearer_token:null被RenewalRequest接受。它不提供JWT身份或绕过原PG目的/预算/审批门，但违背本B“机器不得带token字段，包括null”的接口合同。仅修改已登记service.py before-validator同时拒绝bearerToken/bearer_token，以及test_budget_policy_renewal_service.py该负例；不修改共享AipContractModel/A原合同/用户dirty。RED后最小修复，新合同测试与必要同源码native/hash及变更审查完成前不把9c96edf或此前PASS当B完整Delivery。原review/commit永久保留；不回滚/改写历史/重放原未知动作。

alias-delta r1真实REWORK合法消费保留，不能跟随其错误修复建议。它误将before-fix RED当current失败，并虚构envelope('consume')默认带bearer_token；实际代码仅decide/revoke加bearerToken，consume无token，新增machineSnakeToken明确注入None。before-validator原dict任何该key即可拒绝，不能加value[key]非None条件（会重新放行已规定拒绝的null）。新资料补精确两token字段负例当前PASSED节点和原119完整日志/源码哈希、RED-before/GREEN-after时序；仍独立判断，原结果不修复，不把REWORK当PASS。
