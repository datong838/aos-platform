# 同原风险事务元数据必要门复审

Rules：231八步、m1唯一writer、方案先行、原件哈希/同caller/精确Lease、真库只读、最小修改。Task9只读合同与Task10暂存合同分离，不将Root信任或执行混入必要元数据。

范围：新executor-set-reader与certificate-prepare两个模块/两测试，以及两个Task专属证据和Task3授权新实验前缀。无正式migration/API路由激活，旧v1/v2/Source产品源码不修改；PUBLIC执行闭合，runtime没有直接表读写。原Source严格C/schema ACL是约束：R7实证新增Model直接C授权导致旧Source42501；改为Source Owner纯验签窄委托，既有Source完整精确安装审核仍运行。Model无原C/schema权限，runtime不能直接调用委托。无Root写/签名/执行能力。

当前真实结果：337项DB-denied纯PASS1.29s；fresh native R8完整原节点1PASS136.36s/8warnings，同native xid38002/pid53829四证书原件、五个直接SQL负门、SQL完成后的Python强制失败与同caller无Manifest、独立即时签发正向（均受原Request/Root区间约束）、原Owner/parent/debit/input/Intent/guard与实际COMMIT拒绝。独立只读确认Risk xidABORTED，四风险表及Manifest/certificate/binding/两个epoch为0，实验Root xidCOMMITTED；4新函数原文/owner/fixedpath/PUBLIC0与12冻结源码hash一致，runtime表访问false，原C ACL仍仅两原Owner，Model C/schema访问false。Root bootstrap仍实验，不授权可信Root。

失败完整保留：R1安装順序失败；R2/3/4实际规范原件哈希拒绝；R5preflight无外部效果失败以及原40秒证书最终时钟到期；R6/7核心子步通过但旧Source相邻安装漂移，整体FAIL不能追认；R8独立原件成功不能恢复旧证书或覆盖旧结果。旧两摘要beforeimage仍未恢复，Prime UNKNOWN不重发。所有正式库/商城/Host-worker-Provider/旧Run边界不变。

代码与方案一致：长期实验Root在首snapshot前登记；Manifest/cert/binding在同physical事务暂存，嵌套savepoint覆盖后置Python拒绝；root→所有certificate→identity排序锁，完整组先验后写；原来源再复核、最终实际时钟逐签名复核；旧C封闭授权不扩大。纯委托不写表、不读经营原件、不登记Root。测试与真实终端Scope不可代替formal身份及首链。

未收口：专属canary/非原caller/旧域/撤回/真实末尾到期矩阵、幂等重放version不增长仍需真实精确门；Root谱系和正式安装身份、finaljoint/WALACK/Transport、八工作台自然经营首链独立未验。Task9/10仍ACTIVE，无Delivery；不把本次必要门覆盖成完整Task/长期Goal完成。下一步在现有两Task合同补先保存点幂等和租户边界，再真实撤回/到期；M4/Prime局部故障不阻断授权安全主线。
