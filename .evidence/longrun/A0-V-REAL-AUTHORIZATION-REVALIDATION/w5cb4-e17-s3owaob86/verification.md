# b86 首次来源初始化协调锁交付（不是完整发行）

## 真实RED
red.log：2failed/7warnings/4.93s。普通未发行源先由SERIALIZABLE读取0个撤销事件，RC raw revoke提交后，旧快照仍可提交test-only issuance/head（DID NOT RAISE SerializationFailure）；初始化先行也没有阻止raw writer（实际PID图writer escaped）。测试发行FK fixture不含合法Owner/Policy，不是正式发行命令或当前授权。

## 最小修复与验收
新a0v_139增加exact Evidence FK的中性initialization fence，runtime仅scope SELECT/no PUBLIC，复用安全NOLOGIN owner仅SELECT/INSERT/UPDATE(epoch)；新固定search_path definer锁函数按scope/exact源INSERT ON CONFLICT后FOR SHARE/UPDATE。旧快照面对已提交协调行40001；不能以仅advisory锁替代。原事件trigger BEFORE对所有合法源协调，已发行源再原head锁；AFTER仅实际insert推进协调epoch及已发行head epoch，ON CONFLICT/重放不漂移，异常全回滚。原Python helper统一协调行→已发行head顺序，按DB实际hash取锁；旧未迁移schema仍generic兼容，表存在但锁函数异常不fallback。
协调函数允许普通withdrawn/superseded历史源进行原合法撤销；不在中性锁中新增frozen发行资格，旧正式head函数仍检查exact frozen源。函数只返回协调epoch，不授任何发行/许可权；初始epoch0也不能替代原事件存在核验。

green-first：20passed7warnings10.29s。green-cumulative：105passed8warnings50.09s（9新增初始化专项+原96累计）。新增真实：issuer先持协调锁并提交test-only head，阻塞RC raw writer且其看到新issuance后两epoch都1；raw revoke先、旧SS initializer确切PID阻塞后40001；raw事件rollback无协调/事件；普通同键与ON CONFLICT epoch只1；未发行源锁0但issuance/head均0；Owner函数安全path/noPUBLIC、runtime无直接写/canary隔离、错scope/hash拒；两种历史lifecycle兼容。相邻包括原head并发/幂等/API/严格LOGIN、canonical provenance、schema ACL、原W2A/B Store/API。
signed-full-schema：实际既有签名Receipt+OCI自有测试环境完整schema139 1passed7warnings15.19s，证据读取NO_START。四文件py_compile、精确diff通过。测试库初始/最终49；本轮新owner初始0，结束安全attrs全false/双向members0/共享依赖0后只清本轮角色，最终0；所有session terminal，无旧库/用户改动清理。

## 一致性/风险/接续
不改旧Evidence/hash/原authority，迁移无backfill/no automatic License；新增中性协调行不是影子Owner/License/业务数据真源。b84随机严格LOGIN只额外授新锁EXECUTE，无新增table写/issuance权。138/139均未迁移到当前真实135，未重启/读商城/启动Host/worker/Provider。
剩余完整发行需要精确Owner显式来源许可的原Proposal/Approval、当前签名Policy bytes、独立issuer及完整issuance/head/Receipt事务；已有head或中性epoch0均不是许可。当前Python辅助保持旧domain reason；new neutral lock的EXACT_FROZEN_MISSING沿用旧错误标签，实际冻结资格由正式调用者另核，不据该标签宣称neutral锁已验证frozen。下一继续同b86已登记正式Policy/Approval/issuer，不称本子任务完成整个b86或自然首链。Goal active/authority1329。
