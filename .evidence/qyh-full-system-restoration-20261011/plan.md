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

## 未知与回滚

2026-10-11当前发布来源核对后的安装选型：两个已发布基础包使用现有较新平台1.23.2/operations1.2.2（a0v-local-ecommerce-recovery-v2），与新core1.4.3/Growth1.13.0组合。平台源除version、构建lock/image/SBOM/signature外逐文件相同；operations除version、bundleRef及signature外逐文件相同。需逐项核验已有Registry manifest/artifact/content/signature与保留树精确相等，不能因为contentHash相同更写旧1.23.0/1.2.0签名。新core/Growth只在新坐标由现有RegistryService create→validate→publish；所有旧记录与安装保留。采用登记的有限LOGIN与SET ROLE aos_runtime进行本地维保，actor明确为用户授权维保代理，不冒充正式OIDC/业务Owner。

实际职责分离门：core1.4.3与Growth1.13.0均已由原Registry create+validate；Core同actor的publish被DutySeparationRequiredError拒绝。只读回读两个新版本均validated且无published事件，平台1.23.2/operations1.2.2原published签名精确一致。647表指纹仅五个Registry表发生预期登记变化，其余642表精确保持。请求用户提供独立的现有发布身份，禁止仅换actor字串伪造独立身份。等待期间仅沿独立授权继续来源兼容、安装/浏览器恢复准备；不重发已完成create/validate或拒绝的publish，不改变Goal。

已登记独立目录接线Task qyh-restored-bundle-alias-20261011，修复production allowlist对新不可变alias a0v-qyh-current的识别：仅使用原AOS_BUNDLE_ROOT，不增任意根或权限。90项专项/相邻通过，原有权限连接桩失败独立登记；真实Core/Growth签名树由production映射加载验签且源文件不变。下一安全步骤准备四选定版本的唯一公共bundle目录，文件哈希逐项相同、合并公共信任根、不复制私钥；再做混合版本真实镜像/schema资格验证。这些准备不授发布/安装/业务执行，不把七Growth模块加一operations模块的包解析当八页面验收。

选定公共目录现已独立完成：selected-public-bundles下仅4个精确版本；production两个alias同一根、现有ManifestLoader/ReleasePolicy逐包验签；179个原文件逐文件hash和签名保持，8模块解析。未复制私钥、未修改全局配置/数据库、未启动API。准备脚本首次读取manifest错误字段在intent/目录创建之前失败，核对原BundleManifest.metadata后修正；没有重放外部写。selected-public-root-terminal.json明确mixedImageQualification=false/eightPagesAccepted=false，不继承原1.23.0/1.2.0资格报告为1.23.2/1.2.2组合通过。

下一实际资格步骤新增qualify_selected_candidates.py（仅本Task证据目录）：原resolver固定四坐标，原ReleasePolicy/RuntimeArtifact admission核已缓存精确镜像，原SchemaRequirement/require_installed在有限LOGIN的READ ONLY事务核现有schema；三隔离OciDriver会话按原诊断助手登记/heartbeat/清理，无网络、只读root、无真库mount、无Provider/业务调用。candidate资格策略使用原构建诊断ReleaseRecord投影，不声称Registry已publish；真实Registry两版本validated事实保持。每会话原工具一用journal，若未知容器结果只inspect不重发。输出明确fixture/diagnostic only，不能授Host或安装/运行/八页面权限。

该混合组合实际诊断现已通过：三个精确本地镜像admission、原resolver四版本、恢复647表库READ ONLY三个installed schema receipts符合；三个网络none诊断会话各2048次heartbeat及声明精确登记，清理成功并独立inspect确认资源已不存在，179文件不变。mix-candidate资格首次在加载前冻结时间，被原证据currentness门拒绝、intent和容器均未创建；改为读完所有包后冻结统一评估时间，没有降低原currentness规则。证据mixed-candidate-qualification-terminal.json与mixed-qualification-independent-cleanup.json。Registry两新版本仍未publish，独立发布身份/正式安装配置/API/Web/八页面仍待；这是真实缓存镜像诊断，不是自然业务首链或正式Host运行。

在本Task目录新增release_transition.py、只读preflight证据、有限两版本发布intent/terminal和fresh全库备份（private0600及第二校验副本）。public trust根只合并现有v2与新candidate公钥，不复制私钥，不改全局配置。Publish不自动安装/启Host/授权业务；必须后续当前安装、配置、API、浏览器与实际镜像/schema组合资格门。只有预检证明新坐标不存在、旧2个版本完全匹配、身份/头/Task/无未知操作符合时才能apply。已有intent按结果对账，不能重发。

2026-10-11加载实测修订：Colima未挂载本机/Users配置路径，原docker run退出125；只读inspect证明目标不存在、原容器已正常停止。限定LOGIN已完成且不重放。改用docker create同一命名卷、docker cp无秘密hba到容器root拥有文件（postgres仅可读）、docker start；不依赖主机bind、不改变原卷配置。创建/复制/启动各自记录intent与terminal，失败只读对账。
每次操作intent/terminal。未知只读核对，不重试写；没有运行记录不代替证明。新transport失败先停新候选，不删旧容器/库/卷；原preview仍维持原identity和数据。恢复历史卷不改变original092。API登录/运行门失败只限制该动作，继续安全恢复主线。
