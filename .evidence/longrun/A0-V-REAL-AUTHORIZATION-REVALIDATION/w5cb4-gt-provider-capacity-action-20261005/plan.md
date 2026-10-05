# GT Provider容量申请独立 checker：原 Action 绑定

基线 m1 0587746a / AOS-001347。承接已验证的未批准申请，复习231-5与GT物理共享方案及原ModelEvalAction/AipActionStore，不复制审批表或放宽普通业务门。Task gt-provider-capacity-action-20261005。

精确文件：新增 aip_provider_capacity_action.py、a0v_146_provider_capacity_action.py、tests/aip/test_provider_capacity_action_pg.py；修改原 aip_action_store.py/aip_action_policy.py；本证据目录。先本文件，再实际原申请生产后缺模块 RED，再最小实现及相邻验证。当前 Task 不授现实 Provider 执行。

## 实现要求

1. 注册专用 Object/Action 元数据，R2、makerChecker=true、minimumApprovals=1、draftOnly=false、executionAllowed=false；批准只确认 Owner 申请的配置条款，不证明 supplier limit/账户映射，不签发或激活容量。
2. 复用原 AipActionStore.create_proposal/decide 与不可变 ApprovalEvent，新增 exact native guard；专用 Action 缺 guard、metadata/action ID 不一致必须失败封闭，禁止落入普通通用审批路径。
3. 原事务读完整 request/hash/server maker/固定请求身份/期限，严格 DTO 重parse与正向 scope；DB 当前 Owner、原 Provider exact current canonical payload/head SHARE、原 exact frozen 未撤回 basis 同conn校验。proposal payload 只允许 requestId/requestHash，expiry不得超过申请；禁止 Task/Run/objectRef/impactPreview/diff/evidence/riskHint 伪绑定。
4. maker 必须匹配 request.created_by；checker 原 OIDC 同tenant、当前独立 Owner，禁止自批；maker也须保持当前Owner。风险/metadata/policy/immutable draft/binding hash 不得漂移。wrapper身份校验不能从客户端角色自报授权。
5. 本阶段 basis 仍 owner_requested_allocation、basisVerified=false。独立 checker 检查完整条款引用，不把 Evidence 元数据当供应商上限证明。正式发行/激活/执行后继须对 supplier basis 适用性、稳定 Provider 账户映射和 Source epoch 当前性独立闭合。

## 验证与退出

实际签名 Provider、原 EvidenceBundle build、真实本地 HTTPS JWT、申请 Store产生原记录，再原maker提案与独立checker批准；executionAllowed=false、物理容量/预算预留不增加。补自批、wrong maker/Owner/scope、缺guard、请求/hash/expiry/Provider head/basis revoke/metadata/policy漂移、幂等和canary。原ModelEval/Source审批/普通Action相邻，检查编译与方案一致性。

RED缺模块仅证明功能缺失，不当业务失效反例。申请fixture的test-only Evidence来源不当自然经营或供应商证明。当前142库、Host/worker/现实Provider/Secret/商城源/旧Run/manual/230L0/未知重发/外部效果均不触碰。整体b90八事实实际COMMIT/API/ToolBinding及首链保持pending。

## 独立复审补充

审批期限沿用原decide的min截断规则：最终ApprovalEvent期限不超过提案及申请，不新增不必要的普通规则。实际双checker同key/body回放须绑定原事件actor；先原A批准→B同key的PG RED，再在原decide同事务现有replay分支仅对专用容量Action比较actor_id，普通Action语义保持。初轮hash异常子类/Principal复制错误属于测试驱动错误，期限DIDNOTRAISE说明原截断规则，均不当业务RED。
