# 当前142→151维护合同

依据231主计划、现有142维护方案及完整独立恢复151/第二份142备份验收。当前权威源仍142且完整snapshot未变；API启动门已动态追随代码head151，不修改它。当前m1单写，Host/worker/Provider关闭、不push。

文件：scripts/a0v_current_151_maintenance.py、scripts/tests/test_a0v_current_151_maintenance.py；本evidence目录；aos-recovery/current151-*；明确三个maintenance/current-preview资源。保留旧135→142执行器。先实现纯门禁（Task/Lease exact receipt、不已Delivery、未来expiry、原currentauthority/冻结HEAD、原142源镜像卷/进程fingerprint、151代码head/冻结SQL、九步演练/第二备份hash及snapshot绑定），RED反例后最小实现。旧公共source identity/窗口/进程指纹工具可复用，不放宽旧authority硬编码门。

执行序列：精确原进程停止→隔绝TCP并核listen空/客户端0/prepared0→窗口内独立一致备份和恢复（所有原备份保留）→九步hash SQL一次执行→完整旧数据/元数据和目录允许差异审计、151精确fence→恢复原listen设置并验证→原签名来源最新API/Web启动→端口/启动时间/健康/版本/租户/八工作台浏览器验收。每步O_EXCL intent+终端，超时未知只读对账，不重发；失败保留封闭窗口和原数据，先诊断最小修复；不得未经迁移验证恢复旧不匹配API。

当前仅注册及纯门禁开发；不因Task存在即停止服务或迁移当前库。权限身份/审批预算保持原禁入，不把维护通过当正式首链。

## 只读预检绑定实现
原两个代码文件内补preflight(thread)：新Task身份门→m1/当前HEAD/已提交业务代码→Alembic单head151→九步SQL当前源码离线重生成逐字hash与原intent匹配、terminal0、快照连续→第二backup SHA/globalsSHA/terminal0及独立restore全库窄等价重算→严格fence/native151成功记录作为历史线索（后续当前操作需再次实际验证）→源Docker身份及完整snapshot匹配第二备份→原API/Web进程fingerprint读取→终点HEAD/Task再读。返回preflight only，不提供停止/迁移执行入口。不能把可伪造历史标签单独当权限。

## 现场恢复身份补强
原script/test范围内增加source/second恢复身份纯门及漂移反例；源容器Id+Image+原volume绑定secondbackup intent，secondclone require_target+唯一原命名卷+原镜像，full snapshot现场重读等于原保存snapshot，再与源比较已审等价。仅只读；不提供迁移入口。

## 窗口执行日志
Maintenance151Journal绑定冻结head/thread/Task/base，不仅step名称。原步骤顺序不变；每步前检查所有原done.status=verified及相同binding，O_EXCL/0600/fsync记录attempt后才operation。只有非空dict且status=verified可写done；异常或错误输出只留attempt，后续拒绝重发。仅primitive阶段，不接真实副作用。反例覆盖Timeout后重发、缺前序、head变化、未验证输出。

## 执行时身份复核
每一步在检查历史证据后、写attempt之前，重新读取当前Task/Lease/authority与Git HEAD和m1分支；身份或租约失效不得调用operation，也不产生attempt。写attempt后、调用operation前再次复核，捕获该间隔内漂移；此时保留attempt并只读对账，不重发。真实受控操作仍须自身精确资源复核，这个复核不提供原子Git/租约锁，也不授予迁移权限。RED验证创建journal后的HEAD漂移、Task失效和attempt写入后的漂移均令操作调用数为零。

## 恢复151现场审计
仍只改原maintenance script/test：只读JSON连接适配器使用psycopg Literal绑定参数、仅接SELECT且拒绝多语句，严格把已知OID列/数组与tgargs转换成原驱动类型。调用原require_withdrawal_fence，不改其校验标准；固定原same-image恢复容器/镜像/卷，完整snapshot与a151已保存after精确比较，末尾重验容器身份。将该现场门接入preflight，不能用旧PASS标签放行。该管理员只读目录审计不替代原生issuer身份测试或当前源操作门。

## 最新隔离窗口完整路径
原两代码文件和本证据scope内增加run_isolated151(thread)：先真实preflight；在aos-recovery/current151-*独占0700目录绑定HEAD/Task，固定恢复镜像、colima-aos-a0v-test-only、current151-*新命名卷/none-network/noports。由第二份142已校验备份建立隔离源，再依九步journal执行：无应用客户端→ALTER SYSTEM空listen/restart及TCP拒绝/客户端0/prepared0→窗口内全备globals/dump→新独立恢复并全库窄等价→逐步重新生成已演练hash SQL，每步O_EXCL intent/terminal和版本回读→完整151快照与严格fence→原配置来源恢复/restart/TCP与版本→无应用客户端→最终snapshot、身份、租约/HEAD。任一失败保留所有卷/目录/attempt，禁止重发。此入口不能选择当前源容器，不提供current执行入口；完整当前维护Task仍ACTIVE。

首次隔离九步成功但final snapshot比较RED，只读定位仅a146/a148四新metadata行created_at不同。修正验收：限定精确四ID/两表，旧metadata每行hash不变且count只增加2；原151模板和现场四新增整行去掉created_at后逐字一致，时间须为带时区datetime。只有这些已核行hash与两表总hash可在比较副本中归一，剩余table/count/role/full_catalog等仍原完整比对。首次失败保留，不重跑任何迁移；后续只读调和和未尝试配置恢复分别记录，不能覆盖原verify-attempt。

## 当前资源接入
在原两文件内抽出同一个序列，isolated/current两个入口均强制新Task/未来Lease/预检和committed executable源码。current入口没有可选容器参数，固定原SOURCE_CONTEXT/SOURCE_CONTAINER/原Id+image+卷；仅允许原容器exec/restart/inspect，禁run/rm/volume等。当前调用TCP只读探针走原host18435且只允许SELECT1/version，连接失败才计拒绝。原服务身份复核后各一次SIGTERM正常退出，等待原root/helper消失与端口释放，不强杀；迁移成功后用原argv/签名Receipt预检schema151与空端口启动新root，记新PID/原argv/cwd/端口回读，不凭health200当首链。窗口globals实备后再初始化独立restore目标的roles，使用窗口globals与dump恢复，而非预先旧roles。所有旧备份保留，失败不自动开放窗口/启动不兼容旧API；每次当前操作前复核精确容器和Task/HEAD。运行修订后隔离全路径，再执行一次当前维护；浏览器/上下文/Delivery待实际完成。

## 已迁移151后的独立修复阶段
原window-da8531053c83已迁移151/恢复监听/启动成功，原acceptance失败；不能重跑142预检或原journal。新阶段绑定当前HEAD、同一ACTIVE维护Task/Lease和原失败目录的全部hash；核九步terminal0、之前八done绑定原ebac8fd0、原acceptance仅attempt。租户只读启动代码d7b5ad80已单独Delivery；源码更改需新阶段实际部署，不能把旧服务当新代码。

只修复三既有meta表updated_at：先验证各表原恢复副本与当前恰好一行，org-org/dev-project双边界、整行键相等且只updated_at变化，两时间均带时区且当前时间不早于原值；任何其他字段/行数/租户变化拒绝。生成事务SQL仅允许三固定public表，固定UPDATE一列，WHERE整行jsonb精确CAS，每表ROW_COUNT必须1，否则整事务回滚。已经恢复（时间相等）拒绝重放。不能normalize隐藏旧timestamp，原字段原值必须恢复。

执行门另设新journal：只读核原失败+当前151完整快照（与失败后快照一致）/固定容器卷+最新真实process→新受控停止+TCP零执行→新的完整一致备份并独立恢复→隔离副本演练精确CAS及完整变化限定三字段→当前CAS一次→完整旧数据/151fence验证→原配置PG重启/修复API/Web启动→浏览器及最终完整快照。失败/未知保留attempt，不能重发；本阶段先实现历史/字段/CAS纯门和反例，未接实际副作用入口。原备份全部保留；禁止旧migration、全表UPDATE、角色/ACL/目录放宽、Host/worker/Provider与商城源读。

## 修复阶段执行入口
继续在scripts/a0v_current_151_maintenance.py与原专项测试内实现run_current151_repair(thread)，不提供可选源容器/原失败目录。Repair151Journal使用独立步骤序列，复用原intent-before-effect/精确Task与HEAD复核，不包含迁移步骤；原Journal默认序列保持不变。新phase关联原八已验证步骤/九终端/失败attempt哈希；原进程只有父进程已实际消失可重新登记PPID，其他PID/启动时间/argv/cwd/children/listen全部必须等于原启动记录。新阶段必须代码已提交。

固定原源Id/image/volume及原window restore身份；停止原进程后封TCP，窗口内完整dump/globals、fresh none-network命名卷独立151恢复、完整目录窄等价通过，再在此恢复上精确CAS并要求全snapshot仅三表恢复旧hash；实际源CAS SQL hash与演练相同且一次终端记录。源完成后full snapshot与修复预期精确相等，151withdrawal fence与原模板完整151门通过才恢复原listen、PG重启、修复API/Web启动。最终完整快照不可有启动读取写回；浏览器仍是单独未完成门。未知attempt不得恢复重发；新实例都保留且不push。

当前入口首次预检拒绝发生在claim/stop之前，源库/原服务未动：原142恢复应使用原142 role_names，不能用151新增角色清单做snapshot；full_snapshot的role_names本身是冻结比较输入。只读按原142 roles重算完整窄等价通过，修正该调用参数；原151源/新151副本仍用151角色清单，未删除任何roles校验或放宽原比较。保留current-repair-r1终端失败；没有claim可证尚未进入实际副作用阶段。

## 151修复窗口恢复失败的接续合同

实际phase current151-repair-e1d51a4f1798（HEAD34063052）已完成reconcile/stop/fence/snapshot_dump；independent_restore失败。当前源完整snapshot仍与失败前精确相等，151、空listen，API/Web实际无listener，repair_timestamps从未attempt。新window.dump4594656字节与globals哈希回读通过。独立target current151-restore-05bb402299de已部分恢复603表但pg_restore exit1，server PID88 signal9，cgroup oom_kill1/State.OOMKilled，隔离VM2GB；不能重发其pg_restore或拿603表当恢复通过。

先只读取得终端日志/内存计数后，停止已明确终端的三synthetic proof实例和两GREEN隔离窗口的四实例；逐项核原owner/Task/image/none/无端口/唯一命名卷，O_EXCL stop意图、正常stop与实际Running=false回读；所有卷、容器、备份/结果保留。没有停止原142窗口restore或原same-image151模板（后续核验依赖），没有改隔离VM全局配置或不明归属实例。

下一阶段须新绑定HEAD与当前Task、原claim/四已验证done/失败attempt及备份hash，旧claim不可删/改，不能伪造旧independent_restore done。以新的独立none-network卷完成原151 dump全恢复（内存已释放，恢复session限制maintenance_work_mem/work_mem按实际方案），严格完整snapshot窄等价、原schema上精确CAS演练和严格151fence后，才继续当前同一封闭源上的一次CAS与配置/API/Web恢复。新阶段只能消费真实已验证前序证据，未知结果先只读对账；不能重跑142迁移入口或原restore。原两个安全研发候选仍登记，但优先恢复当前预览服务。局部OOM不设置Goal blocked，维护Task保持ACTIVE。

## 新绑定恢复接续实现
在原两script/test文件内抽出共同_run_current151_repair(thread,recovery)，原入口recovery=False保持原序列，新固定入口run_current151_repair_recovery只接受固定e1d51a4f1798父phase。Recovery151Journal只有reconcile/independent_restore/rehearse_repair/repair_timestamps/verify/restore_tcp/restart_clients/acceptance，不生成或复制父四done。纯门严格父claim/intent绑定34063052、四done、独立restore仅attempt、无后续attempt/所有done；父备份hash再验、实际空listen/client0/prepared0/当前源全snapshot未变、原PID消失/空端口、原监听来源与原window文件相等，才独占新claim。

所有恢复调用新none-network卷，不重用05bb402299de部分target。pg_restore仅此新副本session PGOPTIONS maintenance_work_mem=16MB/work_mem=4MB，保持原768m/1cpu限制，不改源或VM配置。backup_dir指父实际窗口备份，新intent记录父claim/父证据hash，journal前序来自真实核验，不伪造。命令错误先记录私有stderr和exit供诊断，再终止。共同序列后半保持完整快照、CAS逐字hash、151fence、原监听、最新签名API/Web与最终快照门不变。
