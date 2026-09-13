# BG-02 事件控制路由验证

基线 de700b72，m1 单写者。新增固定 ecommerce_growth_event_control，仅由真实 Principal 与精确 PipelineControlServiceFactory 构造的 scoped registry 提供；保留原九操作和原封印。控制服务按需构造，Canonical Router 禁止控制操作走 legacy。HTTP 使用认证 scope/actor；包只增加注册声明，未发布、安装或切换。

验证：首次 RED 为缺失固定控制常量；首轮31项通过；补入控制 HTTP 身份传递后，路由、旧注册表、Canonical Router、控制 Host 数据库和切换合同共50项通过（7条既有依赖警告）。数据库测试使用18432临时库，未迁移18435主库。AR2-7扫描1877模块、分类167、迁移93，所有错误数组为空；git diff --check通过。

证据边界：请求装配测试使用替身，控制Host测试的来源与资格使用替身，不能据此声称真实签名包或真实首链已经验收。未重启服务、未更改活动安装、未push。下一波：领域包控制命令与严格回执消费，随后继续真实事件消费和业务Run连接。
