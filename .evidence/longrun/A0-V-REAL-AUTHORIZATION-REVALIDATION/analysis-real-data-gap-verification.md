# SC4-5d0 栖月汇真实数据与首链差距核对

2026-09-14；代码基线 f9e708ed；m1 单写、不 push。目标仍是自然经营闭环。

本次通过 colima-aos-extension / aos-a0v-recovery-pg / aos_meta_head 的 BEGIN READ ONLY 查询，所有业务统计限定 org-org/dev-project（ecom_object 使用 workspace_id）。只读取聚合计数、表结构和版本，不输出客户记录或凭据，不写业务库。

| 核对项 | 本次实测 |
|---|---|
| 主库迁移 | a0v_038；代码新增039–044尚未部署到主库 |
| ecom_object | Product 65总/57有效；Shop 1总/1有效 |
| obj_instance | Product 57，Shop 1；其余标准对象未物化 |
| 当前管道 | P01-shop-qyh、P02-product-qyh；两条计划 enabled=false |
| Product最新业务源时间 | 2026-06-22 01:05:56 UTC；不能当成最近采集时间 |
| 数据需求/补齐/观察回执 | 三类均0 |
| SourceReadiness回执/AnalystQueryResult | 均0 |
| 来源选择历史 | 2版，最新2026-09-12 20:44:31 UTC |

12类L1首装画像要求 Shop、Product、ProductSku、Category、Order、OrderLine、Shipment、CustomerLite、Weapp、SystemConfig、ProductReview、Payment。2/12是当前物化种类覆盖，不是产品完成率；商品条数也不证明总体完整性、历史截止一致性、来源新鲜度或SSH当前可用。

代码查证：DataRequirementOutboxStore在生产Python代码内没有调用方。现有FulfillmentResumeSaga只消费完成回执而不执行采集；Observation/Hydration Store提供权威持久化入口，不等于自动生产者已连接。ProductQueryApplicabilityReader明确诊断固定商品查询缺少历史快照和总体口径，不能用于伪造全店Fulfillment。

后续实施顺序（纳入SC4-5d）：
1. 复用现有安装配置，形成固定、可版本化的首装数据需求政策，自动从原事件/当前Profile推导意图；不由开发者逐事件传参数，不用预算0冒充成本授权。
2. 扩展当前受控来源路径覆盖剩余10类；先审查12类映射与真实结构，保留店铺过滤、脱敏、软删、源时间、分页完整性与不可变观察。原已签包不改写，新增候选另做验证。
3. 连接原Outbox租约消费者到实际数据Owner：读取当前需求/安装/访问权威，采集、观察、映射、Hydration、Readiness、Fulfillment逐一真实落回执；已知失败可重试，未知结果先对账，不重复外部作用。不能收到队列就直接ack。
4. 实际补齐回执进入现有专用恢复Session，完整sealed Host统一Receipt通过后，连接已有D01/D02/D03实际Worker与方法、披露、预算、Provider权限。
5. 新安装/迁移与服务重载后，以真实主租户运行首链，再扩展八场景和持续观察；当前不作完成或发布声明。

本波为只读差距核对与执行方案对账，无代码逻辑修改、主库迁移或服务重启。下一波先落实第1项的政策来源，确认现有配置承载，再实施最小自动需求连接；并复核全店映射的缺口，避免扩大恢复守卫而遗漏数据生产者。
