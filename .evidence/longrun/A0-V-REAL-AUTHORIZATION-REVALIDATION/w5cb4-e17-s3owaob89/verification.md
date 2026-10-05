# b89 完整受限来源许可发行验证

## 目标与当前范围
原b87 integrated-plan步骤3～5：消费真正独立原Owner批准，用独立来源issuer在一个调用方事务中生成原issuance/head/RegistryReceipt。采用a136原表、原AipActionStore Proposal/draft/Approval event、原RegistryReceipt算法及原签名验证器，没有影子许可、审批或Receipt权威。此交付只证明代码与隔离测试命令闭环，不证明生产Owner权利、正式身份供给、八实际依赖、自然首链或发布可用。
本文件是最新验证记录；checkpoint-in-progress.md的07:38未实现状态仅为历史施工证据。

## 具体代码与自洽性复审
- aos_api/aip_license_source_issuer_contracts.py：仅scope/key/SecretStr JWT及ActionProposal批准精确ref，StrictInt版本>=2、完整hash/id；scope/maker/ref参与原canonical_hash，key和token排除；拒actor/roles/grant覆写、构造绕过和子类。合同仅ISSUANCE_REQUEST_ONLY_NO_START。
- aos_api/aip_license_source_issuer.py：外部JWT真实签名/issuer/audience/expiry/tenant重验在开连接之前；独立aos_source_license_issuer自身SCRAM身份、SERIAL、固定schema/timeout、无成员高权。复用private credential文件校验，不借批准或Registry角色。幂等键→原Proposal/原event共享锁→两当前Owner共享锁→安装共享锁→来源初始化首次独占→原Registry 228/1锁→所有selected version/evidence精确共享行锁。保留原SSI错误，无自动retry。
- aos_api/aip_license_source_proposal.py：严格允许固定新issuer身份，原runtime和批准者检查不删；issuer的来源事实锁从第一次即独占。maker Guard复用原Core完整信封/metadata/风险/请求hash/draft/hash/binding/policy，不复制Proposal/审批算法。
- aos_api/aip_license_source_approval.py：认证adapter仅增精确IssuanceCommand类型，其余原签名算法、批准身份与连接保持原规则。
- alembic/versions/a0v_142_source_license_issuer_boundary.py：新角色默认NOLOGIN；危险属性或成员拒绝，不repair。精确scope RLS、Source Proposal双身份/相关event/draft只读；9个共享锁UPDATE列的实际DML均禁。原issuance/head/RegistryReceipt仅SELECT+INSERT；无批准/撤销/业务绑定或通用运行写权。source_license.issue操作其他身份禁，新issuer其他操作禁；原tableowner维护夹具不作合法授权。原批准/独立event/current Owner/安装/有效窗/无撤销与精确Receipt在INSERT共同校验，Head无覆写。延迟约束在真正COMMIT前验证精确三记录与数据库live有效期；普通Registry操作提前返回，避免要求其他写者具备新Source表权限。旧FenceOwner撤销epoch路径保留。
- tests/aip/test_source_license_issuer_pg.py：合同、权限/危险角色、原操作、孤立Receipt拒绝、Registry post-snapshot原生SSI；完整signed helper包括实际JWT/SCRAM、原批准消费、同键回放、参数冲突、两Owner移除拒、六PID竞争、响应失败/调用方回滚/真正延迟commit拒绝、批准到期/撤回、canary读0、安装过渡不完整/签名证据撤销/来源撤销及回滚恢复。
- tests/aip/test_source_license_approval_pg.py 与 test_aip_license_source_proposal_pg.py：另登记hook Task/Lease，只在AOS_B89_SOURCE_ISSUER_TEST=1时消费已完成原批准；默认b88仍保持issuance0，不改其权利边界。

Native返回先构造，再重新走原signed Policy/完整请求读与live clock；持有事务跨过deadline时，PG延迟约束仍拒commit。发行期限<=原Proposal/Approval/明确validUntil及必需证据到期；额外可选证据不缩小许可窗口。sourceFact仅restricted source license，不是Host/worker/Provider启动许可。

## 新鲜结果与真实失败记录
- red-contract.log：模块缺失导致收集exit2；不计业务拒绝实证。初合同14passed/4.62s，补完整ref字段/tenant/子类后四模块79passed/4.61s。
- red-issuer-acl.log：独立角色缺失，2failed/18passed/4.87s；green-issuer-acl-r1.log：20passed/4.65s。
- red-native-issuer.log：完整私有issuer模块缺失，1failed/20passed/4.57s。
- signed-issuer-r1.log：原issuer正向/回放/回滚已完成，但外层b88旧发行零断言使整体1failed/24.74s；单独登记外层hook并保留默认零路径，r2 1passed/24.76s。
- signed-issuer-concurrency-r3.log：五实际writer等待与回滚，1passed/24.69s；signed-issuer-commit-r4.log：真正deferred COMMIT失败三记录回滚，1passed/25.76s。
- red-legacy-head-r5.log：缺schema旧夹具被新issuer挂Head，实际未抛拒绝，1failed/23.97s；IS DISTINCT FROM明确拒空，r6 1passed/25.83s。随后Head额外核验原source operation/Receipt结果id，不能把维护夹具升为合法发行。
- issuer-stale-registry-r1.log：夹具把requested_by写成created_by，2failed/30passed/5.22s，非运行权限缺陷；r2 32passed/4.94s。使用真实canonical draft行验证原锁算法SSI，不称草稿为合法发布。
- signed-first-issue-race-r7.log：五writer+第二个真实SCRAM issuer六PID等待，第二issuer返回原40001，唯一三记录，1passed/26.17s。
- red-orphan-receipt.log：专用角色仅写applied Source Receipt可提交，真实未抛CheckViolation；补原表延迟三记录约束。此与另一个隔离库同时bootstrap导致后者signed-expiry-withdraw-r8.log tuple concurrently updated/4.53s；两进程terminal后改为串行，不用此结果计GREEN。
- signed-expiry-withdraw-r9.log：真正独立approved后等待DB到期及合法withdraw拒，1passed/29.94s。
- signed-drift-revoke-r10.log：夹具只增加ETag被既有安装单调军规拒绝，1failed/29.98s，未放松原保护；按原三字段单调规则注入“新revision/event尚未完成”的事务故障并回滚，r11 1passed/30.70s。此测试不宣称完成合法卸载转换。
- red-expired-at-commit-r12.log：原批准→响应已构造→等待实际DB到期，真实COMMIT仍可通过，1failed/24.83s；延迟约束增live期限检查，**green-expired-at-commit-r13.log 1passed/7warnings/30.62s**。包括前述正向/回放/竞争/权限/期限/漂移/恢复全链。
- 首次相邻命令漏test_aip前缀exit4未执行，已保留green-contract-adjacent.log。六模块120passed/24.93s后，十五模块green-complete-issuer-cumulative-r1.log **236passed/7warnings/93.85s**；真正COMMIT时钟修复后的最终累计green-complete-issuer-cumulative-final.log **236passed/7warnings/93.08s**，handle44191实际terminal/exit0。可以登记本完整代码波Delivery，不将其当自然首链完成。
- **green-signed-b88-default-regression.log 1passed/7warnings/21.80s**：同a142完整schema，b89开关未启，原b88原批准/竞争/拒绝与发行0保持。
- 八代码/测试文件py_compile及代码、Markdown/JSON精确diffcheck通过；原始signed-expiry-withdraw-r8.log第73行SQLAlchemy生成行保留尾空格，不修改失败日志，也不称含所有原始日志的diffcheck全绿。无页面变化，浏览器验收不适用。

## 隔离、风险与接续
所有PG验收用fixture新建/删除aos_test_*_ti4_test库。JWT真实RS256，只有JWKS网络传输返回测试RSA公钥；两个角色用不同测试SCRAM密码，0700临时目录/0600单link文件，退出清理且NOLOGIN PASSWORD NULL。不是生产IdP、LOGIN凭据或Owner业务权利供给。既有49测试库不删除。最终临时Fence/Approval/Issuer三个角色安全属性/成员0/共享依赖0回读后精确DROP，剩余0；测试库清前/后均49，结果在cleanup-final.json，无DROP OWNED或历史库清理。

当前135真库未迁移/重启；未读商城源、未启动正式Host/worker/Provider，未回放旧12Run/manual run_definition、未触碰230L0或外部效果。九用户M保留，m1单写、不push/其他分支。Authority1329/七强CURRENT/validateGREEN；无新增真实模型调用，agnes r3 assessment6/7/O4限制保留。Prime LaunchAgent PID1844/status0、memory-health observed08:04:37为1329 GREEN_WITH_WARNINGS，仅是本次窄服务读，不外推完整模型/daemon验收。

正式135迁移、正式IdP/Source LOGIN/Owner权利与八配置仍各自独立门。现有readiness的历史license_summary布尔检查不是本完整许可消费，也不是八实际facts；后续必须登记完整正式evaluator/原事务SourceFact消费方案与测试，不能用历史preview GREEN或source fact DTO替代实际经营首链。提醒真实到达与每日09职责保持原规则，Goal active。
