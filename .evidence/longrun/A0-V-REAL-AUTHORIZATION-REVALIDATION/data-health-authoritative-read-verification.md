# 数据健康权威读取验证

基线287ca790；健康页初始及手动刷新复用apiGetAuthoritative，shared hook新增默认false选项，原页面行为不变。新增离线缓存为100分而权威读取拒绝的页面案例先失败；实现后页面32项、网络客户端3项、离线策略11项，合计46 passed，tsc通过。普通离线快照仍可读取，健康离线/网络失败均不回退；不加入写队列。

真实页面上波已在线读出12项未就绪，本波没有人为断开服务注入浏览器失败，网络故障覆盖来自隔离测试。无源库/权限修改。

05:04:22Z持续运行复查FAILED：4359秒、42次续租，三资源unavailable，binding unknown/desired enabled/enabled false/fenced true revision5。不能继续引用上波35分钟健康为当前状态。新证据ecommerce-health-read-continuity.json保留完整观测；下一波优先读取Host v10退出链及Docker状态，确定原因再恢复，不重用已释放generation。
