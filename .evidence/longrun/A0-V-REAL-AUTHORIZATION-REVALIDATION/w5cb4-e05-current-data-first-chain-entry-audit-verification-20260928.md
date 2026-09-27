# W5CB4 E05：当前卷空业务态与数据源正式入口审计验收（2026-09-28）

## 当前证据

只读查询 `aos_current_preview_20260927`：`ecom_object` 所有类型 0、正式 `projection_outbox` 0；`data_source_configuration_revision`、pipeline SourceSelection/RuntimeControl/ScheduleBinding、AutomationOccurrence、AIP Task/TaskRun、D01 proposal 均 0。未读取商城源库或任何商品明细。真实浏览器 `/data` 显示数据源总数 0、无匹配数据源；显示的 12 数据集不是 `ecom_object` 商品数据，不能冒充首链商品截面。已获准安装/四 signed bundle 和 MethodRevision r1 与该空态并存。

## 现有 Owner 和断点

`/v1/sources` 已由 `wave_ext.py` 持久登记 `meta_source`，数据库触发器会生出 `data_source_configuration_revision`，且公开响应只投影元数据；`DataPage.tsx` 有新建数据源入口。其创建使用通用 `apiPost`（可进入离线写队列），异常仅提示重读，页面没有跨刷新冻结同一意图；连接配置保存后自动调用 `/v1/sources/{id}/test`，这会读取外部源，违背本阶段“不读取商城源库”的边界。可见“源配置生产者缺代码”并非根因；产品入口的安全接续断点在调用方式和自动探测。

正式 SourceSelection Owner 已存在并要求当前安装、`aos_runtime` 身份、exact 配置/映射和 ReleasePolicy；`/v1/pipelines/{id}/source-selection-approvals` 路由存在，但当前 Host=0 且源配置/管道均空，不能手工 POST 绕开。`SyncConfigPage` 是通用 schedule 配置，不等于正式 SourceSelection。商品事件消费与自然分析有代码，但依赖新鲜源、获准 selection、安装代、原始 ingress 批次和运行资格；当前不能启动 worker 或造事件演示。

## E06 精确施工选择

E06 先修 `apps/web/src/pages/DataPage.tsx` 的正式登记交互：改用不离线排队的立即 POST；以 tenant+sourceId 持久化不含秘密的待对账标记，未知结果跨刷新冻结，权威 GET 核对同一 ID/配置修订后才解除；移除保存后的自动源连接测试，改为明确的单独获准操作，不在 E06 执行。后端保留 `wave_ext.py`/数据库原 Owner，不新建真源。专项加 DataPage 负例和邻接测试、生产构建；浏览器验证当前无源及安全 UI，不输入真实凭证。E06 完成后再选源配置→正式选择/同步的下一段，真实商城读取仍需用户明确给出最小范围或已有授权证据；不能因本波补 UI 就宣称 A1 通过。

E05 仅审计，未改业务数据或运行 flags。旧 12 Run 仍冻结，未手工 `run_definition`。按 E06 方案编码后重新验证最新代码/当前卷。
