# a144 权限与原三写提交保护施工检查点

2026-10-05，基线99f3a118 / Authority1331。完整Task `w5cb4-e17-b90-full-evaluator-implementation-20261005` 仍ACTIVE。此记录仅证明完整命令的数据库边界，不作为完整b90 Delivery、八实际事实通过、自然经营首链或发布证据。

## 方案与代码复审

- 新migration `services/aos-api/alembic/versions/a0v_144_binding_evaluator_boundary.py` down143；固定evaluator默认NOLOGIN/NOINHERIT/无高权/双向成员0/无owned object，既有属性/成员/owned object/本库显式ACL漂移拒绝，不repair。只读原权威，精确单列锁UPDATE实际DML拒绝。真正写权限仅原binding评估列、RegistryReceipt/proof INSERT；不授健康/Source/批准/预算hold/Capacity reserve/Skill binding/启动写权。Source审批读限定原action和related行。
- scoped表ENABLE/FORCE RLS；AS RESTRICTIVE防旧PUBLIC策略绕过。原未启用RLS表对其他身份保留legacy语义。Health原SECURITY DEFINER epoch API另施加来源session的固定tenant限制，无直接epoch表grant，canary不得初始化中性epoch。全局Capability/Registry/metadata仍按原目录只读，不伪造tenant列。
- 三个真实DEFERRABLE INITIALLY DEFERRED触发器分别挂binding UPDATE、Receipt INSERT、proof INSERT；验证同binding/version/receipt、原operation/applied/resource/result_revision/authority、hash/readiness/timestamps、安装active/current/etag、8facts与Source/Budget/Installation/Owners及原canonical facts hash、数据库live有效期。用原MVCC xmin要求三写均属当前顶层事务，阻止嫁接历史Receipt/preview。新增binding/version proof唯一索引，无backfill或历史删除。
- 完整native命令必须直接在调用方顶层事务三写，不内部commit或分SAVEPOINT；子事务不在当前准入合同。旧writer/preview保持原行为且不会生成正式proof；table-owner测试维护不代表正式业务权限。
- tests/aip/test_binding_formal_evaluator_pg.py：属性/owned object/成员、全列UPDATE ACL、scoped RLS actual flags/restrictive、Owner共享锁实际DML拒绝、canary及Health definer零epoch、真实SCRAM与旧登录门、签名安装上的提交故障。固定角色仅隔离测试期LOGIN，finally恢复NOLOGIN/PASSWORD NULL，保留已迁移共享ACL，无DROP OWNED。
- test_growth_signed_installation_full_schema_pg.py 仅新增显式B90 hook；默认路径无新机制夹具。合成facts只用于机制对照/故障，不当原8facts正向；有效对照SET CONSTRAINTS通过后主动ROLLBACK。所有成功negative都断言失败发生于真实context-exit COMMIT；外部连接核验version1/unknown、新Receipt0/proof0。

## 实际验证与陷阱

| 证据 | 结果 |
|---|---|
| a144-red.log | 2 failed/6.48s，实际PG缺固定角色/三延迟约束 |
| a144-green-r1.log | 7 passed，初始权限/登录集合 |
| a144-green-r2.log | 8 passed/1 failed/7.74s；夹具缺meta_workspace外键父行，补原父记录 |
| a144-green-r3.log | 8 passed/1 failed/7.36s；真实canary能见Owner行，原meta_membership未启用RLS，修补原表策略生效机制 |
| a144-green-r4.log | 9 passed/7.74s |
| a144-signed-commit-r1.log / a144-signed-commit-final.log | 原签名安装机制专项1 passed/33.85s；补phase证据后67 passed/34.58s |
| a144-historical-receipt-red.log | 1 failed/17.10s，DID NOT RAISE CheckViolation，历史Receipt错误嫁接可提交。该隔离合成行只是RED漏洞实证，绝非业务READY；一次性数据库随后删除 |
| a144-signed-mvcc-green.log | 67 passed/35.31s，同事务xmin修补后历史嫁接在真实COMMIT拒绝 |
| a144-signed-control-final.log | 67 passed/35.13s；新增有效结构对照明确ROLLBACK，证明非reject-all |
| a144-adjacent-final.log | 114 passed/1 strict xfailed/58.17s；原Source issuer/proposal、Budget/ModelEval、Capability/Run/Handoff及Health相邻；xfail仍是缺完整evaluate_binding_in_transaction的明确pending合同 |
| a144-health-canary-red.log | 1 failed，DID NOT RAISE InsufficientPrivilege；固定evaluator可通过definer初始化canary epoch，测试finally回滚，未形成当前业务效果 |
| a144-health-canary-green.log | 20 passed/1 strict xfailed/7.36s；固定session的epoch RLS修补后拒绝且元数据0 |
| a144-code-final.log | 最终稳定代码68 passed/35.56s，11边界+56合同+1真正签名PG/OCI fixture，B88/B89/B90全部启用 |

均7个既有warnings。最终8个机制观察含7个真实COMMIT 23514拒绝和1个主动回滚对照，见a144-commit-facts.json，包含实际backend pid/独立测试db及外部读回、角色恢复。测试hash见a144-tested-hashes.json；编译及目标code/Markdown/JSON diff检查通过。PG全部串行，5433测试集群的一次性数据库，旧历史库/卷不清除。无页面改变，浏览器不适用。最后Health策略改变仅新evaluator originating session，原114相邻的其他身份行为不变；最终签名Source及原Health相邻已在该版本重新核验。

## 总体进度的当前真实证据

只读事务回读colima-aos-extension/aos-a0v-recovery-pg，named volume `aos-a0v-recovery-pg-data`，`aos_current_preview_20260927`仍a0v_142；org-org/dev-project活跃安装0、Capability Binding0、Source issuance0、正式evaluation proof0。见current142-overall-progress-readback.json。没有应用a143/a144到真库，没有供给正式LOGIN，没有Host/worker/Provider或外部效果。

完整native八facts消费者、Source两Owner/签名原内容/预算同锁序、所有候选当前性、API/service、幂等重核验、完整原Store签名positive和逐项缺失/竞争/回滚仍待实施；Tool Binding和自然首链随后继续。请求合同、原核验复用和本边界均是同一完整Task的必要施工，整体退出未满足，不收缩长Goal。
