# 本轮提醒142→150最新全栈重启方案

提醒aos于2026-10-05T15:42:01.797Z在唯一thread正式到达。m1 b4727d82/authority1356，真实current aos_current_preview_20260927@a0v_142，colima-aos-extension/aos-a0v-recovery-pg/原命名卷aos-a0v-recovery-pg-data/18435；API PID7130/8080、Web PID7155/8434、Host18181无listener。唯一Alembic head150已提交，无本轮待测进程。不是Goal历史135。

先restore-only Task w5cb4-current150-restore-gate-20261005-154201：新增scripts/a0v_current_150_restore_gate.py和scripts/tests/test_a0v_current_150_restore_gate.py，复用原142的canonical snapshot/backup hash/私有文件/原bootstrap连接读取，不修改原142executor。真实私有0700/0600目录新consistent exported REPEATABLE READ snapshot全备+无密码globals（原生产角色密码不复制）；恢复到独立test-only context新无网络/无端口固定镜像/不同新命名卷，精确比全库旧行、sequence、角色/成员/DB ACL/config、RLS、函数/ACL与元数据。保留所有源卷/备份/目标。

逐步原143..150 offline SQL生成/hash/intent→实际transaction执行→回读单head；不启LOGIN、不业务seed、不Provider调用。每步源current无DDL。固定代码HEAD、当前库/卷/镜像identity；unknown outcome原journal对账，不能改Task/runid盲重发。

预期变化必须由原迁移代码冻结：a146/a148各增加独立容量申请/SourceReview metadata；a143 Health epoch、a144 publication epoch、a145容量request、a147候选与a149 neutral epoch新增表，原历史表行/序列不可改变；a144 evaluator原窄授权/强制RLS/a150私有读锁授权及七原trigger PUBLIC EXECUTE撤除按精确清单审计，不能笼统忽略ACL变化；原runtime正常trigger compatibility已单独测试，新角色全部NOLOGIN/noinherit/nomembers/no高权。已有neutral/health/publication backfill须按实际migration原文审核，不能一律假设新表空。

恢复门GREEN后另登记当前维护资源Task；先精确原服务argv/cwd/启动时间/listener/child/UID和签名receipt回读，再停两原服务、原PG listen空重启/hostTCP拒绝/现client0/prepared0、停写第二份可校验一致全备和第二独立恢复、逐步迁移当前原库142→150、精确旧行及权限预期变化复核、恢复原listen来源并PG→最新m1 API→Web、八工作台浏览器核心只读/安装/租户/禁入。现142runner写死版本与authority，须新正式维护实现和RED/相邻/完整隔离演练后才操作原源，绝不替换常量绕过门。若失败按私有journal已执行阶段只读调和再修复，不改变Goal。

Host/worker/Provider仍关闭；签名安装/禁入预览200不等于正式首链。此Task不交付真实重启/迁移，完整提醒验收及后继publication研发继续待办。


## 扩展比较与精确镜像修复（已知终结，不重发未知结果）

817963e3首capture/restore terminal0、8.589秒、597表旧比较一致，但受邀复核要求补列ACL/结构/其它schema；原报告FULL名称覆盖不足，被补验降级。新full_snapshot只支持实际唯一public用户schema，遇其它schema拒绝；补columns/constraints/indexes/user triggers/显式column/relation/schema/function/default ACL、views/domain-enum/extensions/event triggers共13类。祖先要求无symlink及root/current UID所有权、直属恢复父目录不允许group/other写；既有ai_agent祖先777不修改，不宣称OS强沙箱。固定source Id/Image并在补验期回读；原第一intent未保存source Id不补造历史。

首补验真实13类仅constraints有15条definition差异：source PG16.14/image7e7d...与旧seed clone16.15/image7218...，BOOLEAN AND括号deparse展开不同。不消去括号或忽略约束；原完整备份SHA/原597表/其它catalog仍保留。新source-image-transfer资源Task允许docker image save精确原ImageID到私有0700/0600 archive，manifest须单镜像/RepoTags空，isolated image load按digest验证且所有原tag映射不变；不下载、不改源container/image/tag或已有目标。未知load只inspect原digest，不重发。

随后原restore Task追加已知失败比较后的same-image-target阶段：复用已校验原backup到第二新none-network/无端口/不同卷target，必须使用原16.14 digest，并以13类catalog+原全部snapshot严格比对。原首目标保留；这是已知终结恢复后的版本修复，不是UNKNOWN原恢复重发。每阶段新O_EXCL intent/result，不覆盖原capture/失败/备份。仍不进行当前库迁移/停服务，143..150演练和源维护另门继续pending。


### 原image load只读对账与受控新引用修复

首次save原digest archive成功，manifest单镜像且无RepoTags、config字节hash等于source image7e7d。target为containerd image store；load原archive terminal返回0后精确image inspect仍missing、images仅原两tag，原OCI index无ref.name。该原调用终结，保持原archive和load-intent，不删除/重发原调用。下一固定独立registration step从原verified archive生成derived archive，只改Docker manifest RepoTags和OCI index annotation为预检不存在的aos-current150-source:20261006，其余Config/layers逐字节保留；原标签不得覆盖，独立O_EXCL intent，load derived只一次后精确Config digest+新增唯一tag/原tag-map保持对账。非新凭据/网络下载/源变更。若仍未知或identity不符只读核原step，不重发。该新增引用不重分配任何既有tag；原资源Task仍ACTIVE至真实digest与原映射证明。

### 镜像标识域与内容绑定
源 classic store 的 config ID 为7e7d，目标 containerd 的 manifest ID 为73ab。实际 Config/RootFS/Architecture/Os 已读回一致，原标签保持。执行器使用目标 manifest ID启动，源身份仍核源 config ID；每次重新读取两引擎镜像，核对私有绑定记录的标识及配置/层摘要，拒绝任何内容或平台差异，不以版本号替代。补对应正反例后再执行新独立恢复。

### 同内容镜像恢复的实际结果
44专项/相邻通过。restore-same-image首次调用已终结exit1；新目标current150-same-77f8f834ea15已恢复，随后只读对账旧全库快照一致，13类目录仍仅constraints的15条定义文本不同。故原先“仅16.14/16.15版本造成”诊断不足：同内容16.14恢复仍出现相同deparse差异，需核pg_dump生成表达式及恢复解析的规范化机制。当前不忽略约束、不重发恢复、不迁移当前库，保留该已知终结目标；下一步对比原约束表达式、dump定义和还原表达式，冻结可证明的语义比较方案与反例。整个重启门仍pending。

### 窄语法候选（不作为已验收门）
15差异全部为已存在length下界1、上界160或240的两个原子AND嵌套，后续btrim/正则原子未变。候选只将精确识别的前两length原子括号展开，保持列名、界限、后续全部字节、原子顺序；不处理OR/NOT/一般SQL、不忽略其它结构或ACL。先测试正向与界限/列/OR/剩余条件反例；真实15差异全量复核、方案复审和额外回归前不得将候选接入require_exact_restore。修改仅登记script/test文件。

### 2026-10-06 00:59接续真实比较
原aos_wake_progress按本event执行REVIEW_REQUIRED；当前Goal产品仍blocked，未改状态。原机制角色Task Delivery已另行只读核查，不重复模型审阅。已登记候选：恢复约束比较（原Task活跃、真库只读）与publication方案冻结（独立授权/SQL签名门待冻结，暂不编码a151）。首项实际同镜像全量只读比较597表/4268约束；15差异全部通过窄候选比较、其它12目录及原快照严格一致，证据same-image-candidate-comparison.json；此为候选核查，非恢复门通过。下一步复审识别语法和误放行反例、接入前保留原严格门；当前迁移和重启未执行。

### 候选复审：限制尾部语法
候选原(.+)尾部过宽，虽未接入验收门仍应收窄。只允许同列btrim等式、其可选cntrl负正则，或operation_id固定标识正则；其它SQL/OR/函数/异列一律原文返回。改script及原test，先构造unsupported tail RED，再最小修复。两个候选继续为原恢复Task比较修复与publication方案冻结，选前者；源只读。

### 全库关系类型覆盖门
本轮源只读真实统计r597/i1139/S12，无其它类型。full_snapshot当前逐普通表数据比较，不证明外部表/物化视图/分区表完整数据；明确只支持r/i/S，遇其它类型拒绝。不新增或修改源对象。新增require_supported_relations与full_snapshot前置只读inventory，补f/m/p/I/v/c未知类型RED及真实支持正向。文件仍原restore script/test。

### 独立恢复等价比较合同
新增require_dump_restore_equivalence，不替换require_exact_restore。只对contype=c的已审窄length/同列btrim或固定正则语法规范化，原子顺序不变，三值AND结合律适用；其它约束定义/validated/deferrable/列与ACL、597表数据等仍逐项严格相等。返回明确规范化条目供证据。测试正向括号差异及界限/validated/列ACL反例，实际同镜像读取验证后记录“恢复比较通过，迁移演练pending”，不能完成完整Task。文件原script/test。

### 八步离线演练材料
首安全候选恢复Task的143..150离线SQL生成；第二publication原Task方案冻结（独立授权/SQL签名门未冻结）。本轮先读原迁移文件并用Alembic offline生成每步SQL到私有0700/0600目录，不使用在线连接，不执行DDL。拒绝ambient AOS_DATABASE_URL；非秘密占位DSN仅选择postgresql dialect。每步记录原migration SHA、SQL SHA/字节和from/to，确认8条连续路径，供后续精确delta审阅。离线成功不等于数据库演练成功。

### a143第一步真实隔离演练
仅same-image已比较目标current150-same-77f8f834ea15，none network/无端口/独立volume，执行已摘要a143 SQL一次。源保持只读。O_EXCL intent先于DDL，terminal结果/前后快照私有落盘；失败或未知仅对账不重发。a143预期新增Health epoch表、独立NOLOGIN owner、租户RLS及Health触发/函数，不修改旧表数据，除alembic_version142→143；新epoch初始空。先验证全部旧596表数据、metadata、sequence、旧roles/membership/db属性保持，详细catalog delta另门审阅，不以执行exit0报该步全绿。第二候选publication冻结依赖独立授权/签名门仍暂不编码。

### a143权限与目录只读对账
已执行a143 terminal0、目标143，不重发。全部旧role/db权限/目录记录保持；新增owner NOLOGIN/NOINHERIT无membership，TEMP来自原PUBLIC TEMPORARY不是新增数据库GRANT；owner schema usage是原迁移授权。实际目录增量计数及证据a143-role-catalog-reconciliation.json。新owner仍继承既有PUBLIC函数EXECUTE，需沿a150七旧trigger revoke与owner函数表面继续审查，不称NOLOGIN即无风险。a143源未变，整体演练pending。

### a144单步隔离执行合同
原迁移已复读：独立evaluator与publication epoch owner均NOLOGIN；新增publication epoch空表/unique proof索引；原scoped读表FORCE RLS与legacy/restrict/scope政策，窄SELECT/列UPDATE/两receipt INSERT，原trigger原子三元组门。旧表数据除alembic版本不应变；旧role属性/membership/db设置保持，新增角色db权限单独审计，不能沿用a143目录全不变门。本次只执行已hasha144一次到固定none-network独立目标，O_EXCL意图/terminal/快照，若失败只读对账。权限/RLS语义审阅另门；当前源只读且不重启。

### a144只读差异复核
两新角色均NOLOGIN/NOINHERIT无membership；原ACL/function/policy/db权限行保持。原关系变化仅登记scoped及三Action表ENABLE/FORCE RLS，全部目标逐项回读；scoped PUBLIC restrictive/专用positive政策带固定tenant，新增column ACL均evaluator。证据a144-role-rls-reconciliation.json。实际运行负门与完整权限表面另门pending，不以政策存在宣布正式可用。

### a145单步隔离执行
复读原migration：仅新增不可变request表、strict application约束/FK/租户FORCE RLS、append-only/truncate guard；runtime仅SELECT/INSERT，无容量激活。预计新表空，旧数据/metadata/role/membership/db设置保持；新增表ACL只新表，源未改。本次已hash SQL在固定none-network目标执行一次，O_EXCL intent/terminal/前后全快照，失败未知不重发。候选二仍publication签名边界冻结，先选恢复Task145。

### a146单步隔离执行合同
原migration已复读：无新表/role；保护元数据函数与两trigger、新增ProviderCapacityRequest及aip_request_provider_capacity各1行，原同ID若存在事务拒绝。旧两meta表全行分别读取JSON，只允许新增固定ID，原行逐字保持；其它旧表数据仅alembic版本变，roles/membership/db ACL/sequence保持。固定隔离目标一次执行hash SQL，O_EXCL意图/终结/快照，失败未知不重发；源仍只读。第二候选publication授权与签名门冻结待。

### a147单步隔离执行
复读原迁移，仅candidate不可变表/固定org-org租户/未验证不可执行字段约束、两kind envelope、FORCE RLS及append-only/truncate；runtime仅SELECT/INSERT。新表应空，全部旧数据/元数据/role/db权限保持。固定target一次hashSQL、O_EXCL意图终结快照；未知不重发。第二publication候选仍签名与独立bootstrap待冻结。源只读、不重启。

### a147索引归属与a148单步合同
只读pg_index证明截短唯一索引确属candidate表、valid/ready、列org/project/idempotency_key，原失败是startswith假设，不改索引/重发DDL。a148原migration已复读：仅固定ProviderCapacitySourceReview与aip_review_provider_capacity_source各1条、新函数两保护trigger，旧metadata全行保持，旧table除两meta/alembic不变、roles/db ACL保持。一次固定目标hashSQL/O_EXCL意图、结果未知只对账。第二publication候选签名门待；源只读，不重启。

### a149单步隔离合同
已复读原迁移，无历史回填INSERT：新增独立NOLOGIN Evidence epoch owner/空表、FORCE RLS、3个definer/撤回INSERT的touch+bump trigger；runtime只可EXECUTE lock，无epoch表直接权限。旧表数据/metadata/sequence/membership/db设置保持；旧role保持，新owner权限独立差异审阅。一次fixedtarget hashSQL/O_EXCL意图终结，不重发未知。候选二publication独立签名边界冻结待；当前源只读，不重启。

### a150单步隔离执行合同
完整原migration复读：新增NOLOGIN issuer，不新增表/事实；15表SELECT、5窄列UPDATE/read-lock trigger、tenant positive+restrictive policies、私有Evidence lock wrapper。7明确旧trigger function PUBLIC EXECUTE撤销，但函数体/原trigger/其它named grants保持。旧数据仅alembic变；旧role/membership/db设置保持，旧effective function ACL只这7由true→false；新issuer权限详审另门。固定隔离目标一次hashSQL，O_EXCL意图/结果/快照，未知不重发；源只读。候选二publication独立授权签名门待冻结。

### a150权限与只读canary运行检查
候选一原restore Task的issuer完整表/列ACL与RLS；候选二publication独立签名方案冻结。前者已有150快照：严格15表SELECT且无表级DML、仅原5 UPDATE列；只读事务SET LOCAL ROLE issuer、dev-org/dev-project读13scoped+Action表count应全0，管理员实际原org行count须非0避免空库假绿。不改变LOGIN/auth，不冒充native issuer session；role-level RLS检查无法证明session_user私有入口。源只读，不重启。

### 原生与并发原测试复验
候选一原formal-boundary与Evidence epoch已登记PG测试，候选二publication独立授权签名冻结。首项找到真实test_provider_capacity_formal_boundary_pg.py及test_provider_capacity_evidence_epoch_pg.py，先前issuance_epoch文件不存在是定位失败、已纠正；fixture创建独立aos_test_*数据库并迁移到head，仅test-only cluster5433临时LOGIN/passfile，finally NOLOGIN/清理私有passfile；原恢复clone/current源不改。串行两文件一次、终端回读、结果只证明隔离原功能，不自动完成真实恢复库权限/业务首链。
