# AR2-7D D1 同次店铺物理范围绑定

- 基线aeac0f84；AOS-000571，同一AR2-7D Task/Lease，整波未闭合。
- 方案231-6；维护ecommerce_business_investigation_case_selection.py及同名测试。
- read_bound从既有单店Shop查询同次返回租户、物理platform/shop/external_id与原exact引用；read保持原投影与哈希，无第二选择权威。不拆显示名称、不放宽多店选择。
- Red：新增测试因read_bound缺失失败。实现后店铺选择+查询测量15 passed,7 warnings in7.63s；宿主适配+描述专测16 passed,9 skipped,7 warnings in6.78s。
- 9项PG专测需要专门opt-in且硬编码18432，本次未执行，不计通过；没有为跑测试改变该端点角色或共享库。该切片没有迁移及数据库写入。
- Prime独立只读复审PASS。未证明全集完整、采集新鲜度或实际履约；后续查询须同事务复验exact引用、绑定物理范围与完整统计边界。
- 内置浏览器实际打开15173/workshop/analyst，页面可加载且主导航包含八工作台及工具；当前租户仍无分析记录，因此仅证明入口可用，不是闭环验收。
- 下一项：当前规范库完整有界读取及完整来源身份；已有采集时间列混合语义，需要继续补明确采集依据，不能用查询时间刷新旧数据。
