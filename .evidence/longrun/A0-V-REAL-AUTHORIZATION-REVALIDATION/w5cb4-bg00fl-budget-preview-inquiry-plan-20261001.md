# BG00FL 预算原预览请求只读对账

基线AOS-001026/m1@e9035cd1；Task W5CB4-BG00FL-20261001。复习231-5§5/6/7、419、原BudgetActivationStore/HTTP/Receipt合同。

## 产品与边界
创建预览响应丢失后，现有get_preview需要未知previewId。不能重新POST创建或换key。复用网络提案已有的POST /inquiry只读查询语义，以JSON body提交完整原请求，避免金额/主体等请求内容进入URL日志；该独立查询路由不调用创建方法，真实事务READ ONLY，响应no-store。
只返回历史原preview引用，不返回激活许可。已有只读预览要求当前maker/checker成员，新查询保持当前原maker成员门，不扩大读取权限。预算外部usage证据/原子激活仍未实现，activationEligible永久false。

## 文件级计划
1. aos_api/aip_budget_activation_store.py：抽取原preview request hash纯helper供原create和新inquire共用，不改原写事务/幂等语义。新增inquire_preview按原scope/maker/key查询preview Receipt及preview；READ ONLY/repeatable-read/aos_runtime/双GUC复验。missing→unresolved，原body/checker/head hash不同或Receipt与preview不一致→conflict，exact→observed+previewId/hash+activationEligible false。预览过期仍可观察历史结果，不获得新授权。DB不可用→专用503，不能当不存在。不得调用_replay/加advisory lock/写记录。
2. aip_budget_activation_contracts.py：只读结果两类严格DTO（observed与unresolved/conflict），不输出任意result_ref。
3. routers/aip_budgets.py：POST /activation-previews/inquiry，与原创建同body/key/If-Match及原require_principal；202/200/409及no-store，数据异常503，missingmember403。外部模式禁dev时原鉴权层提前401 AUTH_DEV_DISABLED；允许dev解析时Store仍403拒绝，保持原鉴权语义。不修改其他入口。
4. tests/aip/test_budget_preview_inquiry_pg.py：实际隔离PG/readonly身份与计数不变、原请求找回、body/head/checker变更conflict、未见key/非maker与跨租户隔离、过期仅历史、DB故障不当missing；独立FastAPI+真实TLS/JWT验证HTTP，无mock Store验收。

## 收口/下一波
RED→最小实现→专项与预算activation/authority/ledger/API相邻累计→复审→verification/精确commit/Delivery/CAS/420/D-waves。当前真实库只读、无新migration/重启/Provider/worker/Host/商城源/旧Run/手工Run。
BG00FM接预算decision/revoke响应未知的原请求只读恢复，或根据实测剩余点接产品配置入口；不让后台保存人类JWT，不假造外部usage或激活。正式身份和118到123安全恢复仍独立门。
