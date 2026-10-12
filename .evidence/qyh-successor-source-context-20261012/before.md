# 栖月汇当前160迁移演练与正式恢复门

依据231/用户已批准全系统恢复和当前库安全迁移，thread01a107a2-e9e4-7670-bc44-1144fa9b27e2唯一m1写者。

1. [x] 真实恢复卷/cluster/org读回：aos-qyh-history159-prepared-data-20261011 /7695302940039200809，栖月汇商贸有限公司org-org/dev-project，135安装保留，0绑定enabled，实际schema159。18080GET200但dev登录，formal principal403、外部JWKS未配置；无tokens发行/发布/写入。
2. [x] 精确e17d4fc4a私有API源码原Alembic全revision加载唯一160；不纳入用户改动/untracked/.env。
3. [x] 独立tmpfs clone qyh_head160_rehearsal_20261012从原aos_meta_head159模板全量复制并哈希比对647表，原Alembic159→160成功；646原数据表行数/SHA256全相同，仅版本表预期变化，三新增表空；SourceTemplate647表仍全相同，第二连接读回160且writer无Run UPDATE权。
4. [ ] 此演练不替代当前真实卷最新第二份一致备份/独立完整恢复/零执行窗口；正式160迁移必须逐项完成后才执行，先核签名包schema兼容/权限兼容/可验证恢复路径。真实库本波未迁移，服务未重启。
5. [ ] 正式登录及独立发布身份依既有真实配置入口接入；当前OIDC/writer配置仅键存在性复核，缺少来源信息不虚构issuer或Owner。
6. [ ] 当前四签名包正式安装/八配置/预算审批/禁入复验、最新API/Web和8台真实交互、自然经营首链/恢复卸载重装及连续观察仍待，严禁以本演练或health200计通过。

演练证据aos-platform/.evidence/qyh-head160-restoration-rehearsal-20261012/，提交fba97fc88b45be55a470b9693da691e997ca7a1a。保留独立演练库与private源码；不碰旧12Run、不读商城外部源、不新开Host/worker/Provider、不push，unknown只读对账不重发。


## 2026-10-12 最新161恢复检查点（历史160记录保留）

- 已交付独立容量维护：原Colima data20→60GiB，原真实卷/cluster不变；七实验cluster物理备份/原生WAL恢复通过。实验18431累计测试tmpfs512MiB故障另独立恢复至1GiB，原五保留DB还原，失败fixture数据未宣称恢复。
- 当前真实159最新双备份完整恢复通过：647全数据指纹、完整schema/owner/ACL SQL、12sequence、39role及12user membership等；源未修改。证据qyh-current159-fresh-backup-restore-20261012/verification-r2.md。
- 最新真实副本159→160捕获历史defaultACL arwd导致新3表runtime写权；新增161仅收新3表runtime/PUBLIC表/列权，原旧表/defaultACL不改。80原生专项及相邻PASS0skip，最新副本161原SQL COMMIT，647旧表ACL/columns/policy/trigger/default与646业务/12sequence/39roles全保持；真实源仍159。代码a162a791f、证据042b3f8d8，见qyh-current160-fresh-rehearsal-20261012/verification161.md。
- 当前优先候选一：已授权全恢复内完成精确161与四当前签名包schema/Store兼容复核，依赖完整副本/数据/ACL门已通过；通过后才进入最新正式零执行源迁移窗，不以旧160snapshot跳过。
- 候选二：接入既有正式OIDC/独立publisher身份并走当前安装配置/预算/Owner/禁入/八页，属于已授权恢复范围，但既有配置入口尚待提供，不能虚构主体或凭dev登录授正式权。可继续候选一与已登记隔离producer施工，不改Goal为paused/blocked。
- 正式current迁移/当前m1 API全栈重启、四包正式发布与安装/八配置/预算、8台真实场景、自然首链/观察发布均未验收。已有GET200不计业务退出；无商城源/旧Run/manual/230L0/push/未知重发。

## 2026-10-12 原卷真实159→161维护验收（最新状态）
- [x] 同权威卷/cluster7695302940039200809、aos_meta_head已实际161/650，源迁移证据`.evidence/qyh-full-system-restoration-20261011/source161-maintenance-20261012/r3/source-result.json`。
- [x] 同连续数据库级HBA独占围栏内，新custom双备份与无口令globals双备份hash一致，独立network-none原生完整647 restore、schema-owner-ACL、12序列/原39roles及12memberships匹配；新恢复库原160/161顺序terminal0后，才同SQL迁移源。
- [x] 646原业务表hash/count保持，三个新表为空并FORCE RLS/runtime只SELECT；仅原160声明canonical NOLOGIN角色和单RunSELECT ACL/精确双tenantpolicy/intent FK两内部RI trigger新增，其他元数据/defaultACL/原角色和成员保持。HBA原SHA6271c5b7...恢复exact、reload/解析0；原limited LOGIN与恢复入口preflight通过。
- [x] 新隔离库实际runtime UPDATE越权授权反例被原验证器拒绝，finally原ACL全文恢复、验证器再通过，源650指纹保持。代码/方案复审、实际native专项与相邻完成；commit fa8c36f25。
- 原40角色Lab与首次新clean39 clone终态保留；首次比较器未考虑新FK内部触发器曾拒绝且源无迁移，r3是独立新意图/新库，不重放未知效果。原Stage/User/旧Run数据保持，不改历史executor_stopped。
- [ ] PG→最新m1 API→Web重启仍属于aos待验收；实际管理API仍旧冻结代码/dev只读，目录0，不能把健康GET200当八台恢复。独立入口review格式仍未通过，既有正式OIDC/独立publisher配置路径待答；当前四包正式安装、八配置/Owner/预算、八台真实场景、自然首链/连续观察/发布均未验收。


## 2026-10-12真实发布、安装请求与接续复核

- 原权威同卷同cluster已159→161，实际PG/API/Web预览重启保持650表业务指纹；八GET页仍禁入，不能称全系统/自然首链完成。
- 更正旧“Registry发布必须先等待企业OIDC”的范围：既有实际user:dev开发管理员有aos publisher scope，原服务允许admin且满足与持久化创建/验证主体分离。本轮Core1.4.3/Growth1.13.0真实publish，四签名包和八UI定义完整；只有两Registry表变化，其他648保持，两份一致备份保留。
- 当前八工作台后继安装ab2fd72f-d81c-400d-bbbc-e1589a159d6b：原resolve/create/submit已真实提交，四精确包/3边/8UI、绑定407revision5前驱，state=submitted；真实栖月汇安装管理页显示该请求。尚未approve/apply/verify/configure，原maker-checker不能用同user:dev自批。原其他3admin成员不能当认证凭证，已有登录入口问题待答；不重复请求全恢复授权。
- 本轮安装后置对账误写预期receipt表名而失败；原store实际使用bundle_installation_command。只读回读submitted和前驱保存，六变化皆原控制面；原intent未重发。证据.evidence/qyh-current-admin-install-20261012，提交0c75ba267/e36f8b9f3。
- 父Task checkpoint旧迁移input hash因后续禁字节码修改失配：取实际fa8执行版本并核旧hash，保留旧proof与污染snapshot；当前0511冻结源原consumer接受，迁移/重启/publish/submitted按各自真实范围记录，不修改原观察器。
- 新独立entry质量复核r4：现有Prime身份/agnes-2.5-flash、tools0、原严格JSON三claims PASS，实际原consume成功，execution_authorized=false。模型行号部分错误已人工核实际函数与范围，不称全部模型质量或正式业务验收；旧attempt未重发，建议未自动授权。证据.evidence/qyh-restoration-entry-review-r4-20261012，提交fea7795f8。
- 下一已登记主线：真实独立审批→原apply/verify→当前Source/Owner/预算/八配置及资源门→八页实际功能→自然经营首链与连续观察。局部审批缺口不改变整个Goal状态，当前Goal官方读回active；Host/worker/Provider保持关闭。

本轮两独立只读成员来源分类：其他3admin不匹配原canonical maker/checker或恢复maintainer公开actor；来源未分类，也未证明可登录，不能冒充。仅现有user:dev已真实认证。


## 当前Source接线代码波（2026-10-12 6f93c7a9b/7f30d3078）

原Source连接/protocol隔离复验18PASS0skip0xfail；r1测试迁移postgres身份被161日志owner门拒绝，r2受支持原rehearsal租约和正确18431/aos_app配置复验；Source650不变。部分是最小schema协议，不称全Source验收。

新增aip_source_issuer_wiring.py：3purpose私密精确目标配置，默认未配置None保持旧行为；显式错误拒绝，原串行化Source连接不重写、不借Runtime/Owner。三个router分别注入原Plan/Contract/Content factory，原caller/Source业务校验不动。实际FIFO阻塞RED后O_NONBLOCK拒绝非普通配置文件。60专项/相邻PASS0skip0error，含3真实隔离Role连接COMMIT/scope重绑与API/Store正常行为。

真实源role/ACL和650表0变化，新Source配置及凭据未激活。最新已提交代码6f93独立冻结8646文件、原consumer接受；父Task已核唯一旧PID55416一次SIGTERM/空端口，原只读入口新PID75128/session23263实际加载。QYH安装请求submitted可读，POST405/canary404/两目录0；真实浏览器安装请求可见、customer仍禁入。未重启PG/Web、未开Host/worker/Provider、不重发旧Run。

下一已登记实施：完整Source固定操作SQL权限、generic/BI/successor/Content/Contract真实全调用方兼容与当前完整恢复克隆切换，不能直接撤旧Runtime写权限求目录绿；当前SourceACL/stageReady仍false。独立安装审批/应用/核验、当前Owner/预算与8配置/资源、八页功能和自然首链均pending；整体Goal仍active。
