# SC4-5L6Y3b-1 当前组定义执行守卫

目标是停用后原任务/重启恢复也不能继续取得读写许可。Y3a领取检查仅是入口；现有SourceClaimOwner是Ingress/ControlledJournal/Store恢复共同的原current边界，在该边界补守卫。主库061不升级，不调用真实源；m1串行、不push、230L0挂起。

## 合同

SourceClaimOwner的current回调内，原源控制先持有installation锁，再验证组定义，最后原run锁。对于没有组归属且从未是定义v2领取成员的原单路，保持原行为；发现当前归组但没有原v2领取，拒绝。对于v2领取的Run：从不可变成员表找到唯一原group，完整读取并校验回执、请求actor/control/run映射；读取十二个最新binding并与原请求一致；原enabled exact定义/head、执行人、当前成员归属、单路enabled均一致；原GroupOwner重验完整十二控制公共窗口，持有定义及schedule锁直到本次事务结束。

不能因当前成员已释放就把旧v2 Run当无组单路。source claim重放、saved恢复、completed复核均经过该守卫，不允许改key创建新组绕过未知结果。原source claim/完整input回执仍由原Owner维护，此守卫不创建源claim、input或Store写。

新增 aos_api/pipeline_snapshot_schedule_guard.py；最小修改 aos_api/pipeline_source_claim_owner.py 在原current回调、原run锁前调用。新增 tests/extension_runtime/test_snapshot_schedule_execution_guard_pg.py。旧024专用schema夹具缺新组表，若回归需要，显式在该fixture命名无组guard，不给生产加缺表回退；完整064测试使用真实新表。若需要调整其他fixture，先登记路径。

负例必须证明新守卫价值：配置停用后人为模拟旧入口又把单路enabled=true，仍不允许SourceClaim；归组外来Run无v2回执拒绝；最新binding变化拒绝；原source claim存在时停止后read_current/read_saved_current/read_completed_current不可绕过。正例enabled全组原SourceClaim预留及重放保持幂等且无实际源读。再跑原native组claim/输入/恢复与专用schema旧Claim回归。

复核补充：仅有current守卫还不能允许组Run走单表prepare，否则破坏整组一致快照。新增单表prepare专用拒绝，凡原组领取成员或当前归组成员均不能进入单表源读取；组对象阶段resume_saved不受此入口拒绝，继续受每事务current守卫。最小补改 aos_api/pipeline_controlled_snapshot_ingress.py 两阶段当前控制回调。旧专用schema夹具 tests/extension_runtime/test_pipeline_source_claim_owner_pg.py 显式命名无组两个guard，严格只用于旧024路径，不计新组验证。

组身份复核补充：原PipelineSnapshotGroupClaimOwner还能收到调用方group_id/控制运行列表，仅逐Run守卫不足以证明它们属于同一个原调度领取。故在 aos_api/pipeline_snapshot_group_claim_owner.py 原操作入口调用SourceClaimOwner的组守卫：存在原schedule claim成员时必须同原group_id、同actor、完整exact 12对，不接受任意新group或子集。无原调度claim的旧native路径保留，逐Run current仍有效。专用024夹具第三个guard同样显式具名无组。

恢复限制登记：exact原定义/current绑定要求会正确拒绝窗口到期或绑定续期后的旧组。当前Y3b只承诺同一有效权限内的提交/进程中断恢复，不能把现有单路saved window renewal直接套用为组恢复许可。新增Y3c任务：正式组恢复授权Receipt，精确关联原group/旧定义/原input与仅窗口续期的新控制，重新核业务上下文不变；未有该Owner前到期保持禁入，绝不改原claim/ref/hash或新建组假装恢复。Y3c补入主组调度清单，在Y4/Y6真实恢复验收前完成。

## 结果（2026-09-16）

Red明确复现停用后legacy enabled=true仍可reserve（/tmp/aos-group-execution-guard-red.log，DID NOT RAISE）。SourceClaimOwner每次current回调已接guard_snapshot_schedule_run；验证不可变原组、当前exact定义/十二绑定/完整当前控制/成员enabled，再原run锁。source恢复与completed读取同样受限。单表prepare两阶段拒绝所有原组成员；整组claim入口验证原group_id和完整exact控制/Run列表。没有缺表/权限失败回退到单路。旧024专用schema夹具三个guard明确具名无组，不能作为新守卫证据。

原组合执行首次12 passed后因native_ingress模块重复导入session autouse建库夹具，发生meta_workspace初始化缺表；这不是产品失败也不计通过。拆开该模块单独进程，不改生产、不弱化数据库。整组native claim/completion初次18 passed/290.11秒（/tmp/aos-group-execution-guard-native-v2.log）；组身份补强后最终12新guard+4native claim+1完整完成重放共17 passed/116.46秒（/tmp/aos-group-execution-guard-final.log）。独立原input lost-ack/unknown/partial原子恢复4 passed/24.00秒（/tmp/aos-group-execution-guard-input.log）。显式AOS_EXTENSION_PG_TEST=1的旧单路claim/ingress/saved recovery/组ingress共50 passed/12.72秒（/tmp/aos-group-execution-guard-legacy.log），非skipped。

git diff --check通过。无主库升级/host重载/真实源调用，Y3b-1守卫完成不等于运行器接通。下一波Y3b-2按sc4-5l6y3b2-snapshot-runtime-plan.md复用原Ingress→Completion；Y3c窗口续期恢复权威已补回原Y清单；之后Y4–Y6及Z/真实经营首链八工作台继续。m1独占、不push、230L0挂起。
