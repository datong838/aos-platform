# 内容与活动正式输入只读接线

Rules：用户方案先行/最小更改/保护dirty和数据；231总控串行唯一m1写者、八步Loop、真实数据和原稿、独立Prime冻结合法消费。复习231产品L1/L5/L6与文件级/八步合同、231-4只读租户及旧API兼容，交接和D-wave前序结果。不把内部管理投影冒充最终领域隔离运行方案。

Task qyh-content-real-inputs-read-admission-20261014，owner codex-01a13484-f019-7d82-94ce-812396db9124，base AOS-002027，Lease06:00UTC；另一个原卷维护Task仍ACTIVE，两个scope不重叠。当前HEAD6c9b65777eec4ab0688fa50a318e40b0a9b05d9b，router/test无dirty。

## 问题与审计

真实OIDC页root content-campaign200而real-inputs404；source inventory确认该GET仍CatalogDependency。不是认定预算过期导致404。已交付ReadCatalog是legacy成功先返回，legacy404才延迟读取selected当前签名安装与ecommerce.workshop.read；保留租户、角色、markings、模块校验，不让请求选择安装或任意module。

仅 `/v1/ecommerce-workshop/views/content-campaign/real-inputs` 改catalog注入ReadCatalogDependency。_reject_query_parameters和_require_content_campaign_installation保持；reader调用仅用已认证principal org/project。旧POST/workflow/其他未审计GET仍CatalogDependency。

传递链：router默认EcommerceWorkshopContentCampaignInputs；产品/库存connect_read_only(inherit_scope=False)，apply_transaction_scope受信TenantScope，参数化SELECT ecom_object、deleted_at/cutoff/类型过滤、最大200行；只返回公开有界字段/ref/hash而非raw properties。campaign_store默认独立db_read_only_connect，read_snapshot限定cutoff/limit100，savepoint隔离plan/calendar/content失败；_list_current_on_connection与_list_content_variants_on_connection均SELECT，租户/cutoff/版本hash和Receipt校验，无publish/create/consume/外部Connector。SQL表名是服务器固定调用常量，不来自HTTP。产品和campaign是两个只读事务共享时间cutoff，不宣称跨事务单一MVCC快照。unavailable/partial/blocked按现存DTO保留；未知stock不补0。read_snapshot已有辅助content读取属既存canonical库只读，不读取商城源。

## 文件、实现与验证

唯一产品改动 services/aos-api/aos_api/routers/ecommerce_workshop.py：这个函数catalog类型一处替换。测试 services/aos-api/tests/test_ecommerce_workshop_read_http.py：扩展精确GET白名单一项；RED验证拒绝read catalog先到且业务reader不调用、已接纳后受信tenant传递、未知query先拒绝、原POST仍legacy不触consumer。相关真实contract/inputs相邻现有测试复用，不伪造native业务证据。

先独立方案复核合法消费，后RED；最小实现后read_http/read_catalog/content_campaign_inputs/authority snapshot相邻回归。正常原角色READ ONLY native可走原管理环境，不DDL/seed/预算。维护Task负责最新冻结API加载与owned浏览器正常GET：root200/realinputs正式DTO或真实partial/blocked、菜单/原稿同态差异，无POST。浏览器页面已关时先核实际入口再正常只读连接，不重放未知旧操作。

专项通过之后独立代码/证据复审，不以stub到达证明真实业务完成；精确提交自己的router/test/evidence，不能stage用户dirty或私人source/credentials。准确Delivery仅这个读取切片，Authority CAS需其他当前Task先准确交接基线；不能令并存Lease失效后消费旧review。同步项目/Prime强投影而不写个人Codex记忆。每步记录证据及真实缺口。

## 风险、回滚、剩余

ReadCatalog是管理读取接纳，不是runtime可用/预算授权。原DB161/650保持只读；Host/worker/Provider OFF、旧12Run不重放、disabledSchedule不启用。DTO中ready只是现存read状态，页面生成/批准/发布须原独立门，当前management wrapper仍405。不删除来源缺失提示以掩盖缺口；视觉遮挡单独Task先方案。回滚未发布注入与新增测试，保留历史不可变证据，不重签/覆盖旧版本或改DB。

其余十条辅助GET、完整预算C/用户本人exact批准/正式部署、自然Case/Run分析→方案→内容能力→人工续跑→总控Wiki、八真实场景、安装全生命周期、观察发布全部未完成且保留。每日最新m1同原卷PG→API→Web、aos-2不重启照旧。
