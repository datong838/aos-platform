# BG00FX 预算费用批准原子消费及风险限制接线

基线AOS-001038/3e22b3ee；复习231-5费用与恢复、FQ/FS费用提议合同、431、budget store/reservation/development authorization、network119/120受限consumer先例。当前库只读，只在conftest隔离PG迁移。先计划后代码；本波不部署正式OS/DB凭据，不启Host/Provider。

## 必须同时解决的两点
1. a0v111仍全拒active INSERT；不能只改为允许共享API。新独立caller/NOLOGIN owner、专用SECURITY DEFINER函数，caller无表DML/无membership，原共享publish仍拒active。
2. 风险提议还绑定Provider/model/perRequest/total/maxRequests，现有reservation只读日/月限额；激活必须保留精确来源并在预留/提交前强制风险门。未完成接线前不能把active当运行授权。

## 文件级实现
- a0v_126_budget_cost_consumer.py：consumer call/owner默认NOLOGIN/NOINHERIT/无高权限，无成员关系；精确RLS/列权限；不可变budget activation Receipt只允许专用函数owner写；active INSERT仅专用caller/owner。迁移前须无历史激活Receipt并检查角色无漂移。降级禁止破坏历史。
- aip_budget_cost_consumer.sql：read-committed、scope固定org-org/dev-project、锁同issuer的proposal advisory以消费/撤销序列化；按当前原maker/checker权限、原提议hash/账户/period、批准/撤销/期限、当前draft Head/target、Provider exact current source校验；budget head FOR UPDATE，其余source/member FOR SHARE；最后重验clock。head/revision/唯一Receipt同事务；原proposal+decision派生稳定key，重入只历史Receipt，不授权新写；任何失败整体回滚。独立caller不接受payload/actor/任意key，输入仅exact refs。
- aip_budget_cost_runtime.py：新成本来源预算以activation Receipt为入口，精确关联提议/decision，保留risk限制与撤销/当前source约束；核pricing Provider/model，perRequest风险不超，累计count与风险占额不因unknown或已释放而自动清零；同预算串行锁避免并发超量。旧无cost activation Receipt预算保持原规则，缺表/漂移失败封闭。
- aip_budget_reservation_store.py：在新预留以及提交前接入风险检查；历史查询/结果对账不得因批准撤销被阻断，unknown不重发。只改必要调用点。
- aip_budget_cost_schema.json：只根据隔离新迁移catalog生成候选并审核差异，允许新受限owner只读policy/ACL，不从当前库采纳baseline；issuer原guard/表不可变不变。
- test_budget_cost_consumer_pg.py：真实独立低权caller登录+TLSJWT issuer；一次消费/并发唯一Receipt/整体回滚/撤销优先/期限/错scope/role/source/head/member；核existing store读取与runtime风险/多调用/unknown。test输入不是正式用户授权。相关issuer/schema/product/reservation回归，禁止旧专用PG环境绕隔离。

## 收口及风险
新后端无页面变更浏览器不适用；RED→实现→专项/相邻累计→复审→verification→精确commit/Delivery/CAS/432/D-waves/AOS+Prime。正式身份/安全备份克隆零窗口迁移仍独立波；生产当前库不得更新。若本轮未全部完成，Task保持ACTIVE，按实际检查点接续同一FX，不把子步骤称波次GREEN。后续补producer UI、独立消费进程与正式授权安装自然首链；不绕过模型/价格/网络/配额完整运行门。

## 实现复审补充
- 新aip_budget_cost_runtime_fence只在消费事务创建，runtime仅SELECT/UPDATE(version)，行身份不可变且version只能+1，revocation同事务推进；旧SERIALIZABLE快照在锁此行时必须40001，不能仅依赖advisory+旧快照。新预留在桶锁等待后检查风险，所有counts包含held/submitted/unknown/settled/released，不自动恢复风险额度或次数；历史结果查询不受新授权检查阻断。
- 所用development价格必须携带exact Provider/model/decisionId authorization，其窗口不超过原target；每次预留精确等于批准perRequestRisk。proposal expiresAt限制激活消费，已消费授权执行期使用target有效期，同时每次检查撤销、当前成员和Provider。依赖现有运行Owner验证模型实际调用与价格/预算配置，不增加Provider调用。
- 必要配套文件补充：aip_budget_cost_preflight.py把新fence表和两个trigger函数纳入catalog封板；pyproject.toml增加*.sql包数据，避免安装后缺SQL资源。新表实测default privileges附送INSERT/UPDATE/DELETE，已经显式REVOKE再GRANT列权限，重新审核隔离candidate差异；不采纳正式库结构。
