# Evidence 撤回与容量 Source 审查提交协调验证

基线 m1 523b83bc / AOS-001350。Task gt-provider-capacity-evidence-epoch-20261005；仅此子任务交付，完整Source和b90继续ACTIVE。

实际问题：原SERIAL Source审查末次读取后暂停，原revoke Store成功提交，再放行审查仍成功批准。red-confirmed.log 1failed7.58s证明两者实际成功而顺序未协调，不是mock两次调用。

实现：a149新增独立NOLOGIN/no-membership epoch Owner、private FORCE RLS表及固定search_path三函数，原撤回INSERT前取得write锁、成功插入后递增；Source同原caller锁旧request/account/basis的全部Evidence，稳定排序去重再重读exact frozen/nonrevoked/hash。runtime无epoch表权限，只有窄reader EXECUTE。原License先于neutral，原通用tenant撤回保留。autocommit/未开启/只读/repeatable-read拒绝，唯一精确RLS policy/ACL/Owner/函数源码/trigger注册核验。没有改变原ProductionStore或旧license purpose授权。

## 新鲜验证

- transaction-policy-red.log：实际autocommit和ALTER POLICY USINGtrue两反例2failed8.75s；修复后adjacent-r5.log Source26/epoch16/原Evidence18合计60passed61.92s。
- final-epoch-license-r3.log：epoch22与原LicenseAuthority/Initialization27合计49passed40.64s。实际Source reader-first阻塞原writer，有pg_blocking_pids确认reader身份；审批提交后原撤回成功。writer-first和旧SERIALsnapshot拒绝，无成功审批。真实三不同bundle及排序、重复ref去重；并发首次初始化SSI失败回滚；直接INSERT rollback/commit/冲突replay与原API replay仅成功插入推进epoch；reader初始化rollback。非positive tenant原正常API/SQL撤回兼容，Source canary拒绝。
- 实际table/column/functionACL、functionbody、triggerdisable、OwnerLOGIN/membership/extraGrant漂移均拒绝；epoch runtime SELECT/UPDATE/DELETE/TRUNCATE拒绝。
- compileall四文件、精确git diff --check通过。无页面变更，浏览器不适用。
- 受邀route_supervisor复审确认两次整改、最终日志和方案一致；后台自主报告/连续值班仍未验收。

## 测试编写/审计错误与修复记录

green-r1.log是首次边界审计把epoch自身TOAST对象计作额外所有权的setup错误，修复仅允许本表自身TOAST/index，不作业务RED。final-epoch-license.log两失败是测试误用keyword-only函数位置参数；final-epoch-license-r2.log一失败是追加测试时错放rollback代码块导致NameError及原测试内容缺失。均已按真实源码修正，最终r3完整通过；不把中间失败日志当GREEN或业务缺陷RED。

## 限制及后继

epoch只是撤回顺序，不证明供应商限额、账户归属或正式签发来源。审批先提交、随后撤回合法，后继consumer必须重验当前性，不能继续执行已撤回依据。新增DDL尚未部署当前真实库；仅disposablePG5433。当前142库无访问/迁移/重启，无Host/worker/现实Provider/Secret/商城源/旧12Run/manualrun_definition/230L0/未知重发/外部效果。

正式账户归一、供应商适用性/时效/private issuer身份与签名/consumer拒绝candidate继续下一fullSource Task；共享occupation/旧占用切换/预算容量一次Intent/transport/Usage/Report/Gate及b90完整8facts真实COMMIT/API/ToolBinding、自然首链/八工作台/观察发布继续pending。m1单写/no push。

提交审计：代码文件精确diff检查通过；整份staged diff检查提示原pytest失败传输的行尾空格。原始logs按原字节保留，不将整份日志diff称为无警告。代码提交4247f5c7，日志空格不影响执行证据。
