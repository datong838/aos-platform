# 本轮只读维护与下一读取入口

Rules：完整231目标、唯一m1写者、用户dirty及原数据保护、原业务库只读、方案先行、逐波八步Loop、精确冻结独立Prime及合法消费。长期Goal仍ACTIVE；不缩为重启/测试/页面通过。

本轮原Authority AOS-002027及当前Task qyh-daily-readonly-schema-compat-20261014读回一致。只剩本Task当前有效Lease，owner codex-01a13484-f019-7d82-94ce-812396db9124，到06:00UTC；旧owner仅历史过期项，不抢锁或重放。

HEAD6c9b65777eec4ab0688fa50a318e40b0a9b05d9b。API78287实际cwd为该HEAD冻结源码、18080监听、原management-readonly入口与本次source report参数匹配；Web78346实际entry为本次web-server.mjs、18434监听，764冻结文件逐一SHA匹配。初始spawn回执terminalVerified=false不改写，另以raw-runtime-readback-r2.json及live-verification-20261014.json独立补证。

原PG同CID、原命名卷aos-qyh-history159-prepared-data-20261011、cluster7695302940039200809、schema161、650表、启用绑定0。纠正流程重启StartedAt02:56:36UTC；before/afterPG/afterBrowser/finalReadonly全650表行数与内容hash完全相等。只读最终snapshot新label已实际执行，未重复备份/恢复/迁移。

真实OIDC org-org/dev-project八root200及历史Case只读有原请求证据；Case r14/Run CANCELLED/0 of3/not_started/SourceReadiness blocked不是经营完成。11辅助GET404、视觉差异、子区加载与完整页签/滚动仍未验收。owned页已关闭；当前不能宣称新补拍成功。

现场Prime r1 NEED_EVIDENCE保留并严格合法消费。新增原process/cwd/port/argv、全指纹比较和原浏览器GET路径补证；r2包超固定65KiB未形成请求/模型attempt，原包保留无修改；r3 PASS严格合法消费于live-review-consumption-r3.json，execution_authorized=false。不得把此PASS作为原DB部署、预算同意或Host/worker/Provider许可。

新auxiliary-get-source-inventory.json逐一匹配11实际404到9个GET函数；router工作文件与committed HEAD完全相同，均仍CatalogDependency。只说明接线差异，不自动确认所有404同根因或服务传递只读。

## 下一安全施工入口（先登记、复习、审阅再编码）

候选 `/views/content-campaign/real-inputs`：get_ecommerce_workshop_content_campaign_inputs默认构造reader；ecom_object读取采用connect_read_only、TenantScope/apply_transaction_scope、同cutoff和有限条数；campaign_store.read_snapshot默认db_read_only_connect，并用只读连接上的savepoint隔离部分失败。仍需完整下层SQL/序列化/错误映射核对。不得调用publish_campaign或任何command方法。

预计最小产品文件：services/aos-api/aos_api/routers/ecommerce_workshop.py，仅该GET注入已交付ReadCatalogDependency；services/aos-api/tests/test_ecommerce_workshop_read_http.py，验证runtime安装下该GET+租户/禁入/非法query/POST门保持。相关inputs/store源码若审计发现写副作用，另在方案明确文件后处理，不能隐性扩大修改。

当前Task不持有上述产品文件或D-wave范围，所以**未修改产品代码**。下一步先正式新Task/不重叠Lease及文件方案/D-wave登记、完整上位产品技术方案复习、独立方案审阅，再RED和最小实现、专项相邻、原角色只读native和真实浏览器、冻结Prime、准确Delivery/提交/Authority/Prime同步。其他十条辅助/private GET继续逐条，不一次替换全部Catalog。

本维护Task仍ACTIVE，无新的正式Delivery或Authority推进；完整浏览器收口与全恢复未被伪称完成。已交付A/B仅闭合预算代码候选；完整C及唯一用户实际exact预算审批/正式部署、自然CaseRun首链、八场景、完整安装生命周期、连续观察与发布决定均保留。原DB只读、Host/worker/Provider OFF、旧12Run/disabledSchedule/商城源/外部发布禁止不变。每日最新m1同权威卷PG→API→Web和aos-2不重启约定持续。
