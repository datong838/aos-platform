# 维护身份门阶段

新增门禁拒绝Owner/thread/base/authority/status/Delivery/缺Lease/重复Lease/receipt漂移/过期或无时区/资源范围缺失。13项新测试通过；相邻累计52passed1failed，旧测试使用当前live authority但旧执行器硬编码AOS-001329导致预期scope消息变成authority拒绝，不修改旧门、不宣称相邻全绿。新Task真实read_task成功，scope及Owner未来Lease一致。

仅实现身份预检，尚无服务停止/隔离窗口/当前迁移入口；代码Schema/备份/演练/源身份和进程绑定待接入。当前权威源和服务未改；Task保持ACTIVE。方案和当前阶段一致，测试只证明身份条件，不能证明迁移完成。

## 真实只读预检接入
已在当前真实环境执行preflight：原Task identity+未来Lease、m1/已提交业务源码、单Alembic head151、九步当前源码离线SQL hashes逐项匹配原执行intent、terminal0和snapshot连续；第二backup/globals哈希与terminal0、独立restore全库窄等价重算；源当前full snapshot==第二份backup source；原service进程fingerprint；结束重新Task/HEAD无漂移。13纯身份测试通过。
当前尚无mutation入口，也尚未将native/strict-fence历史记录转成操作前现场门，源image需继续与backup intent绑定、实际独立restore现场snapshot重读；不以本只读GREEN授予服务停止/迁移权限。已记录live-preflight.json真实读回，不称完整维护完成。

## 现场资源与窗口日志阶段
现场源Id/Image/唯一volume匹配第二backup intent、secondrestore身份镜像卷固定、现场full snapshot等于原saved再窄等价验证源，实际只读GREEN。资源5反例RED后GREEN。新journal实际文件测试：Timeout只留intent、重发operation不调用；head变化拒绝前序binding、failed结果不生成done。最终20passed；这些纯执行器边界测试不证明真实窗口/数据库迁移。
尚未接入真实stop/fence/备份/迁移operation；服务当前运行，源142未改。newTask保持ACTIVE。

## 执行时身份复核检查点
创建journal后的HEAD/branch/Task漂移反例真实RED：三例均已调用operation（调用数1，期望0）；另外三例因新复核入口缺失失败，18passed/6failed。最小增加每步写attempt前与写后两次实时Task/Lease/authority和m1/HEAD复核。专项24passed；专项与旧维护保护累计63passed/1deselected。唯一排除为既有旧执行器硬编码1329、测试依赖当前1369权威的错误消息断言，原失败仍保留，不宣称旧整套全绿。

真实只读`_require_live_binding`通过：Task/Lease/AOS-001369/m1@465fa10f一致，证据live-journal-binding.json；没有调用journal operation，没有服务或数据库副作用。方案与实现均明确两次采样不是原子锁，真实operation仍须自身资源复核。完整当前迁移/重启/八工作台与自然首链未通过，Task保持ACTIVE。

## 恢复151现场原审计器接入
适配器缺失RED3failed/24passed；首次真实preflight在原审计器多行SELECT被适配器错误拒绝（SELECT后换行），原失败log保留。补一个换行RED1failed/27passed后最小修正为SELECT后允许空白，仍拒绝多语句。专项与旧维护保护67passed/1deselected，旧1329消息断言排除原因同上。

真实第二次preflight退出0：同原source142与第二份备份/独立142恢复均完整回读；固定same-image恢复库151完整snapshot精确匹配a151保存after；原require_withdrawal_fence逐项检查列/约束/RLS/owner/function body hash/ACL/额外权限/trigger/立即外键顺序通过；结束Task/HEAD再读一致。证据live-restored151-preflight-r2.json及对应log。没有修改业务审计器，没有开放LOGIN，没有迁移源或停止服务，mutation_permission仍false。管理员只读审计不代替原生issuer身份或完整业务授权；下一步按原合同接零执行窗口与受控维护操作。

## 最新完整隔离维护窗口验收
代码408d82fe建立完整隔离路径，资源5个反例RED后专项/相邻72passed/1deselected。首次真实隔离运行在current151-window-942e6cab76d9：停写/TCP拒绝/客户端0/prepared0、窗口全备与独立全恢复、143..151九步terminal0；最终比较RED，只有146/148四新元数据created_at差异，旧行/目录保持。失败记录与封闭的隔离卷全部保留，没有重跑旧迁移。

代码a44685b3：四已登记新增ID仅created_at允许带时区时间差；payload/旧row/未知ID三个反例RED后专项/相邻75passed/1deselected。以实际四原整行与新整行只读调和确认其余字段一致，完整snapshot窄等价通过；这不是首轮整序列通过。

独立新卷current151-window-e322c5b61a71实际完整序列47.49秒、进程exit0：九个journal done全verified，九步migration exit0，每步预期版本及原冻结SQL hash验证；窗口备份/独立全恢复、完整151旧数据和目录（仅四新增created_at归一及已审15CHECK结合律）、原严格withdrawal fence、恢复原listen配置来源并restart/TCP schema151、最终资源/完整snapshot/Task/HEAD通过。原dump、globals、两新恢复卷均保留。证据isolated-window-r2.json/log及journal-summary.json精确hash绑定。两无应用阶段仅isolated_no_application_clients，不当真实API/Web重启。

本Task仍ACTIVE，没有Delivery；当前权威源142及现有API/Web未改，source_touched=false。完整当前维护入口/真实零执行窗口/源迁移/最新服务启动/八工作台浏览器仍未通过；Host/worker/Provider关闭，正式业务首链保持pending。方案与本阶段一致，不把隔离47.49秒当当前维护通过。下一立即将相同已验收步骤接入固定当前资源与精确原进程控制。

## 151启动后修复准备检查点

2026-10-06 HEAD d7b5ad80只读复核：源151完整snapshot与原失败后保存快照精确相等；8080 PID28946/8434 PID28993仍原11:45启动服务。三meta表各一行，字段差异仅updated_at。原acceptance失败不覆盖、不补写done，不重发九迁移/启动。

新增build_tenant_timestamp_repair151仅生成SQL，无执行入口/不授权限：精确三表/原org-org+dev-project/每表一既有行/只updated_at/带时区且向前漂移；全事务、固定一列UPDATE、整行JSONB CAS与每表ROW_COUNT1否则RAISE回滚，已恢复相等值拒绝重放。RED9failed，专项及原维护相邻91passed1deselected0.36秒。排除的是原维护1329固定Task反例与当前1369冲突，未宣称旧全套通过。

原生PG独立none-network新卷证明：timestamp-cas-native-proof-r3.log/json exit0，第二行在CAS冻结后实际变化令SQL异常并首行变动原子回滚；恢复测试准备后正向精确三原值恢复；重复已恢复请求被生成门拒绝。只是假数据三表事务专项，不等于当前151真实schema/目录触发器全恢复演练。首轮因测试容器名不符合原隔离门拒绝、未执行DDL；二轮因错误反例直接篡改生成输入被纯门提前拒绝、未发修复SQL；失败日志/独立卷均保留，没有放宽门或重放未知结果。

timestamp-cas-current-readonly.json使用原window独立142恢复的三既有行和当前151实际三行通过纯门，仅保存行/SQL hash，不暴露实际身份字段、不执行SQL。原数据时间戳仍未恢复；服务未加载最新代码。后续必须新绑定阶段、当前HEAD/Task/原失败证据与精确资源、零执行窗口、新一致备份+全恢复、真实schema副本演练后才精确执行当前CAS；不得用本专项替代该门。

当前完整维护Task保持ACTIVE，未Delivery；权威/Prime当前1369需在维护阶段收口后同步实际151状态，不能沿旧原HEAD重放journal。未操作当前源数据库、原服务、Host/worker/Provider、商城源、旧12Run、manual、230L0或push。

## 独立当前151修复入口

run_current151_repair仅固定原源/原failed window，先精确八done/九migration terminal0/acceptance-only attempt、原142恢复full snapshot、当前失败后full snapshot、原资源与签名启动来源、现有真实PID/argv/启动时间/children/listener校验；原父进程消失才重新登记PPID。当前HEAD与源码已提交门、d7b5ad80祖先、Task/authority/未来Lease复核，独占且fsync claim拒绝第二次入口；不会补写原acceptance done或重放migration。

Repair151Journal独立11步默认原Journal不变；新历史门RED7项失败，最终99passed1deselected0.38秒；wrong-thread入口无资源调用、历史缺记录/非零terminal/换源/已acceptance拒绝，原未知intent保护相邻保持。代码whitespace检查通过。精确三字段CAS已独立原生回滚专项通过；完整当前资源序列需下一实际运行证据，不把单测算完整维护通过。

入口复审：source每次操作核原容器Id/image/卷/端口，窗口PG本机Unix读操作不开放TCP；新dump/globals/fullrestore只在新none-network卷，原全部备份保留。restore演练SQL与当前SQL逐字hash相同，当前只有一次CAS终端，后续严格全snapshot与原151fence/模板通过才恢复配置、PG/API/Web。源码commit后运行，任一失败保留封闭窗口/attempt供只读对账。

## 实际维护窗口与OOM诊断

新入口第一次在任何claim/停止前因为142恢复角色清单参数错误而拒绝；只读按原142 role_names全库窄等价PASS，修正调用、99专项/相邻通过并提交34063052。第二次实际phase e1d51a4f1798已完成四步骤，完整dump4594656字节和globals hash验证；独立新151恢复遭OOM（signal9/cgroup oom_kill1/容器OOMKilled），exit1，不能宣称恢复通过，未执行当前CAS。原副本、原attempt、数据卷都保留。

current-repair-oom-reconciliation.json实际全库快照未变、schema151、listen空、API8080/Web8434实际无监听；源数据仍原启动后状态（3updated_at待恢复）。已按原owner/Task/none-network/image/命名卷身份停止七个本Task的已终端或已GREEN测试实例释放隔离VM内存，全部保留卷；不涉及本机源或原备份模板。证据两个memory-release.json和私有逐实例stop-intent。当前维护Task ACTIVE，不Delivery；新恢复阶段需新HEAD绑定并明确消费真实四done，不能重放原部分restore/claim。

## 原窗口恢复接续入口
新增固定run_current151_repair_recovery，共同后半CAS/fence/startup/最终快照逻辑复用。Recovery151Journal只消费原四真实done与原claim/hash，拒绝已restore done、任何后续未知attempt、错binding/claim与失效前序；新8步骤不复制/伪造父done。精确旧PID/children已退出+端口空，源完整snapshot仍相等、原配置来源同原window、原SQL hash匹配、OOMKilled实际容器证据、备份hash再验后才独占新claim。纯门RED7failed；最终106passed1deselected0.38秒，代码whitespace通过。

复审原_run_sequence151 AST与本修改前HEAD精确相同；恢复仅新副本pg_restore会话限制maintenance_work_mem16MB/work_mem4MB，原源码接口不接可选容器/父路径、不改源或VM配置。错误先落私有stderr/exit再终止，原未知效果不能重发。源码提交后再执行；实际恢复/当前CAS/服务启动仍须新现场证据。
