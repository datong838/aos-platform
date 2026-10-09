# 完整v3准备态描述的新证书域

基线085e4097f / AOS-001673，原typed与atomic Task ACTIVE且Lease仍有效。两个登记候选：v3新签名域/完整描述与原风险origin/身份必要绑定（本波）；actual token与最终joint（依赖真实输入及WAL语义，继续调查但不猜权威）。

仅产品 `services/aos-api/aos_api/aip_model_eval_execution_contracts.py` 新增v3 SharedParentRisk certificate/signature envelope/canonical signing bytes与必要crypto验证；原v1/v2函数与类不改，未跟踪历史reader不夹带提交，不动DDL/迁移/Issuer注册或任何runtime权限。证据在本typed目录；原atomic目录新增fresh native实验，不动已有实验原件。

签名输入含完整manifestHash、原风险hash、完整prepared描述hash、caller xid/pid、execution/case/purpose、该腿原申请hash/candidate/全leg以及Issuer/publicKey/区间。无每腿金额或allocation。Target绑定原Target申请，Judge绑定新目的Judge申请（candidate仍来自原Judge governance目标）。bytes使用独立v3域。prepared描述必须全typed/canonical相等；既存origin/原风险/完整案例/原申请不可挪用，证书截止不得超出新目的原申请。

验证只做真Ed25519/区间/显式撤回集合必要检查，presented issuer不是可信root或native epoch。本波无Issuer/identity head查验权限扩展，不宣注册、COMMIT、joint或调用权。下一步必须通过原private v3身份绑定与same snapshot currentroot/certificate/identity撤回路径，不能自动让旧v1触发器接受v3。

RED新入口缺失。纯检查覆盖两case四leg真签名、旧域拒绝、origin/风险/描述/hash/申请/purpose/identity/Intent/joint漂移、假签名/根/过期/撤回/非法bool。native fresh Source+独立100秒批准双父原Suite，在实际prepare描述前将两purpose描述公钥设置为新实验实际Ed25519公钥，实际risk/description生成后签全4证书并核绑定，再保留真实COMMIT拒绝与独立ABORTED/0回读。公钥/签名落证据，私钥不落盘。Root仅实验presented root，rootProvenanceVerified=false/metadataCurrent=false/executionAllowed=false。原50秒失败与受损历史摘要限制保留，Task不得DTO-only Delivery。

实验隔离完整性修正：R1辅助库路径少退一层，加载失败；R2四leg签名及提交拒绝通过，但相邻旧节点缺original_source_plan_fixture_r1.py失败；R3复制第四个原辅助文件，保留R1/R2原日志结果。修正均在新实验目录，不改旧产品/原测试或回放未知效果。
