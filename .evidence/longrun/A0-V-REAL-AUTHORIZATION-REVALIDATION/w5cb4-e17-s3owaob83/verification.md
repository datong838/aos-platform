# b83 生产来源fence/撤销与事实读取验证

## 实际RED与已修复

- 四个夹具门失败不算业务RED：直接active插入违反draft起点；draft无revision/lock提交FK失败；缺meta_workspace；CreateInstallationRequest采用camelCase alias。复用原Composition/Installation Store及既有输入helper建合法可提交draft，未禁用guard/补假active。失败原log保留，不改称业务缺陷。
- 有效raw-event RED 4.46s：旧136图中真实runtime插入event后(头epoch,event,Receipt)=(0,1,0)，预期(1,1,0)。仅暂移本写者自己的137 migration，finally恢复，真实一次性库而非mock。
- pre-replay RED 4.76s：有事件fence、去掉Store前置锁，两个确切PID均经等待图抵达控制head后释放，一个真实23505。最终原型probe同时禁用新key锁才代表旧算法，不冒充单一source-lock独立幂等证明。
- wrong-hash RED 4.77s：exact hash分类让已发行bundle/revision错hash被当generic，插入未拒。分类改数据库tenant/bundle/revision；Store锁数据库真实hash，原请求hash仍用于replay/conflict；trigger验证NEW exact source，错hash42501/零effect。
- cross-resource idempotency RED 4.80s：同key两个不同源各锁head、同读空Receipt，受控Receipt条件gate释放后真实23505。Store新增tenant/operation/key事务advisory锁置于source锁前；一成功一原IdempotencyConflict，失败者0/0/0；字段/authority hash不改，PG hash碰撞只额外串行化。
- domain-error RED 4.94s：缺head/错hash裸42501；最小固定原因白名单映射LicenseSourceUnavailable→原ProductionContractDependencyBlocked，既有router422。40001不吞不改；raw trigger42501原子回滚。

## 当前验证结果

- 最终来源专项16passed/7warnings/9.82s（source-final.log）：真实role/ACL/固定path/无member/全表before+after trigger；event只实际插入才epoch+1，ON CONFLICT DO NOTHING不漂移；Store同键重放/不同body冲突、新key已有event仅新Receipt；first-event precommit时确认1/1/1再throw→0/0/0；两writer同键均成功1/1/1、跨来源同键一409冲突一成功且失败源0/0/0；双方锁顺序/旧SERIALIZABLE snapshot40001、exactPID等待图；普通源不minthead；missing head/错scope/hash/无head写；真实API缺head422+零effect；缺函数/无EXECUTE安全域错误+零effect。SQLSTATE对应内部PG失败与API域合同区分。
- 累计76passed/8warnings/44.65s（green-delivery.log）：当时来源13项+b82/b81/b45/普通撤销/原W2A/W2B Store/API。之后仅追加上述API/缺函数/权限3tests，无生产代码变更；最终16来源专项覆盖新增项，不称一次77/79全量运行。前轮API73passed1failed44.07s来自旧s3owal夹具brief_ref/marking={}污染正常列表，修为合法test-only ref/list，生产解析不放宽；b82旧全表1行前提改精准fixture及before/after不变。
- 签名实际active installation full-schema 1passed/7warnings/15.05s，SOURCE_FACT_ONLY_NO_START正向、期限边界、实际撤销epoch/event、随后REVOKED拒绝（signed-source-fact-final.log）。原安装/签名/Owner链走原实现，issuance/policy/Owner refs仍管理员test-only fixture，不是合法发行授权。生产签名reader仍EVIDENCE_ONLY_NO_START/preview PREFLIGHT_ONLY_NO_RUNTIME_START。
- 135兼容最后1passed/11deselected/7warnings/4.54s：一次性库head严格135、issuance表不存在，当前Store正常撤销/重放1event1Receipt。仅临时将自己的136/137迁移移出图并finally恢复，未真库降级/升级。此运行在最终安全错误映射前；该映射仅trusted domain锁异常，135走table不存在分支不变。原136文件diff零。
- 7文件py_compile与git diff --check退出0。测试库计数开工49/最终49；新固定NOLOGIN owner开工不存在、所有test DB已drop后shared依赖0且无权限属性/member漂移，才清本轮自建role；role-cleanup.log最终owner0、库49。没有清历史库或既有role。当前真实命名卷135未迁移/重启；无UI更改，浏览器不适用；没有Host/worker/Provider/商城源/外部效果。

## 方案自审与未完成边界

新独立NOLOGIN fence owner只读source/issuance/head和UPDATE(epoch)，不拥有发行权限、不继承aos_runtime；runtime仅受限lock函数EXECUTE，trigger函数不能直接调用，FORCE RLS与schemaqualified固定path。BEFORE取共同锁/AFTER实际插入推进，raw SQL也不能绕过epoch；请求key锁在head前，避免不同资源的Receipt竞争。普通Evidence业务合同/旧hash/Registry角色不改，部分新schema不给generic失败降级可信域。降级拒默宽权/关fence。

来源Fact检查exact冻结source/issuance/head、撤销、期限与当前安装etag/active-current一致；它不是signed安装准入、当前Owner/policy权威验证、正式Issuer身份或执行许可。外层命令仍需先锁安装/registry，再稳定排序source heads，在caller事务复用for_transaction重算八维与actual Health/Capacity facts、CAS/Receipt/proof。其他八维writer还未同锁；fixture不是发行来源；当前proof schema JSON八键不是canonical事实验证。整体Goal active，真实自然首链pending。

下一b84：先定位原Owner/policy/签名发行权威与现有Receipt guard，再整合可信发行初始化的身份、事务/幂等、source canonical验证、安装与Owner/policy锁、受限数据库写命令；不能仅再交付一段连接/空服务或503占位。普通runtime+非空license_summary+自报policy/Owner拒，旧revoked源不得重发或reset epoch。合法独立issuer正向与回滚/replay/canary必须真实PG证明，当前实际135迁移/正式身份供给继续独立门；若某源缺许可，继续其他已登记安全项，不暂停全Goal。
