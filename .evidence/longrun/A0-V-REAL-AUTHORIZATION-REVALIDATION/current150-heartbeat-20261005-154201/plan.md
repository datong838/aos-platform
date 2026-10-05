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
