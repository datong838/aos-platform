# 模型联合依赖校验

基线 3cfbaf90，A0-V m1 Lease。require_model_dependencies 先回读 exact active quota/budget，存在开发授权时验证当前模型的 Provider exact ref、model ID、批准依据、租户及有效期。

5 个负例先红（原实现未拒绝），实现后联合校验、策略合同与 ExactProviderInvoker 回归共 42 passed。覆盖模型/Provider/批准/过期/租户漂移，匹配与旧策略兼容，并确认两条策略依赖仍读取。测试使用依赖替身，无 DB mutation 或 Provider 调用。

源码接入点为 AipModelRuntimeStore.publish_model 和 AipExactProviderInvoker._guard_dependencies，均调用此依赖方法；没有额外路由或客户端授权判断。未核价 active 放行和费用结算状态仍未实现，不宣称该整链完成。既有 7 项警告及 JDBC 测试退出日志问题保留。
