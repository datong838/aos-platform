# BG-02 消费器平台工厂验证

基线d4c4b47d。新增PipelineControlServiceFactory.build_event_consumer，共享selection Owner，固定scope/actor/run/controlRef，ControlledIngressJournal为saved_recovery=True，固定core InstalledInvoker，使用已有runtime连接。构造不读取源、不提交、不启动任务。

RED缺工厂方法；装配、原HTTP/scoped registry/控制路由/三阶段流程24项通过（7条既有依赖警告），装配测试权威对象为显式替身。AR2-7扫描1881/分类168/迁移93，各错误数组空；diff通过。没有生产调用者/后台worker注册，不能标真实自然触发完成。

下一步运行生命周期异步消费入口，使用平台当前live job作用域，不能写死QYH租户或从web默认身份枚举数据。已有同步管线executor不临时创建事件循环。未部署/重启/主库变更/push。
