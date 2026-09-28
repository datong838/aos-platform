# W5CB4 BG-00c｜技能放行事件独立 Owner 路由

## 方案与现场

复习 231-1/9、AIP BIND-3：evaluated Skill r1 需 exact EvalReport → passed ReleaseGateDecision → PublicationEvent(target exact r1) → governed publisher 复制为 immutable published r2；不能直接改 lifecycle 或伪造 GREEN。当前正式库 `aos_current_preview_20260927@a0v_111` 中 EvalSuite/Run/Report、Gate、PublicationEvent、Logic publication 都是 0，37 Skill 全为 evaluated。

现有 `AipReleasePublicationService.publish` 已能核 SkillTemplate evaluated revision/hash，但唯一公开 POST 是 `/v1/aip/publications/logic`，名称与 Skill 发布不符；前端没有正式 Skill 放行事件入口。新增明确技能路由时必须在 **写入前** 验证 gate target 类型为 SkillTemplate，且 replay 也不能跨类型复用同一个幂等键。此路由只消费当前真实 passed gate，不生成 EvalReport 或 Gate，不代表正式来源齐备。

## 文件级最小方案

- `services/aos-api/aos_api/aip_release_publication_service.py`：`publish` 增加可选 `expected_target_type`；若指定，在 existing event replay 或新 gate 读取后校验 exact target type，不匹配抛现有 `AipReleaseAssetUnsupported`，提交前失败，无新事件。
- `services/aos-api/aos_api/routers/aip_release_publications.py`：新增 `/v1/aip/publications/skills`，沿用严格 `PublishReleaseRequest` 与当前认证/租户，调用同一 Owner 并指定 `AssetType.SKILL_TEMPLATE`；保留旧 `/logic` 行为，避免影响既有合法客户端。
- `services/aos-api/tests/aip/test_aip_release_publication_service.py` 与 `test_aip_release_publication_api.py`：先 RED；隔离 PG Logic gate 请求 skill route/type 必须零事件拒绝，重复键跨类型不能重放；路由必须转发 target kind、tenant。相邻 E2/BIND 相关回归。

## 边界

本波只提供正确的正式 Skill 发布事件 API 合同，不对当前库写任何 Gate/Event，不用 dev-org 作正向验收，不手工 Eval/Run，不启 Host/Provider。下一波做当前 EvalSuite/Report 的合法生产产品链及首链必要来源；正式正向只在真实 Owner/批准齐备时发生。browser-pilot 无可调用工具时不做手写 CDP。
