# BG00FS 独立预算费用风险签发

基线AOS-001033/a24568ba；复习231-5审批/费用/unknown、231-9开发授权、425/426、FR以及network issuer auth/connection/a0v118。Task W5CB4-BG00FS-20261001。

## 角色与来源语义
预算域独立aos_budget_cost_issuer默认NOLOGIN/NOINHERIT/无super/createdb/createrole/bypassrls，仅可SET ROLE aos_runtime。新decision/revocation/receipt由DB触发器要求session_user专域issuer及current_user runtime、双scope、无额外角色；普通Web/runtime、network issuer不能签发。不存在自动创建正式登录/凭证/进程，当前实例继续禁入。
费用批准语义为批准FQ精确development风险提议，实际费用仍未知，既有占额/限次不释放。不声明账单完整性，不发出Provider请求，不把approved当BudgetRevision active。当前精确Provider head+payload/hash/lifecycle需存在并active；modelId是审核覆盖的未来调用目标，实际模型注册/路由/secret/价格/配额/网络完整依赖仍须运行前验，不要求预先active模型BudgetPolicy重造首次循环。外部statement仍无正式Owner，拒绝。

## 文件级计划
1. a0v_125_budget_cost_issuer.py：独立NOLOGIN角色，decision/revocation/receipt不可变同scope表与FK/唯一键、RLS FORCE；INSERT触发器签发身份/角色/scope门。原未批准proposal表不改，批准另存，no backfill/worker/downgrade。
2. aip_budget_cost_issuer.py：严格SecretStr JWT command（operation decide/revoke、exact proposalId/hash、key；decide显式approved/rejected，revoke reason）。复用external OIDC配置检查与resolve_principal，逐次验签，token不入hash/Receipt。DB factory必须显式传入，无共享owner默认；每事务再验session/currentrole/GUC/role属性、read-only+isolation。
3. decide在SERIALIZABLE下锁原proposal命名advisory、当前maker/checker成员、actor只能原独立checker、重建canonical提议、exact hash、expiry/head/ledger；approved还核同事务当前Provider head，原始payload hash和scope/id/revision/lifecycle一致。写一条decision+Receipt；同key/hash回读；不同key同proposal不得再决定。revoke允许原maker/checker当前成员，决定必须approved，写一次revocation+Receipt，与decide同锁；历史不改。
4. Inquiry仅原actor/key/operation/hash，READ ONLY/repeatable-read及同scope；missing unresolved、drift conflict、observed只历史ref/eligible=false，DB失败明确unavailable，不重发。读回核immutable结果/proposal/hash及actor，撤销不清除原批准。
5. test_budget_cost_issuer_pg.py：独立隔离PG，临时实际登录（私有pgpass，角色密码不打印）和真实TLS签名JWT，不SET SESSION伪造正向；复验普通API账号拒绝/网络域拒绝、maker同人/非成员/变更head/Provider/过期、Receipt回读/重复key/撤销、无active写；数据库不可变与NOLOGIN默认。故障注入仅测试库，不接真实Provider。

## 下一步与风险
本波是签发核心与数据库边界，不部署正式OS进程，不新增共享API直连issuer凭证。BG00FT补私有连接配置/独立进程IPC/精确部署预检与产品原请求恢复；后继受限consumer锁当前source/head/撤销原子写active+唯一Receipt。新代码125只能隔离迁移测试，当前实例118旧快照→125需独立备份克隆零执行窗口安全波。m1精确提交/Delivery/CAS/427/D-waves/Prime，无push。

复审补充：来源/head锁可能等待，批准写入前再次读DB clock；DB INSERT门同时核原提议hash/checker/expiry及当前clock。追加等待跨过到期的RED、真实Receipt trigger失败整笔回滚、network登录负向、三表RLS/不可变/普通runtime伪造负例。签发核心不接受默认共享DB工厂；私有连接配置/超时/IPC大小限制与生产OS身份属于BG00FT部署接线。
