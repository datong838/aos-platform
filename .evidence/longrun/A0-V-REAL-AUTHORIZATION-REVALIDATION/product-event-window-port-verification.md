# BG-02 已安装核心包窗口端口验证

基线a2098ed2。精确CurrentInstalledPackageInvoker+固定core包+固定操作；一次调用、深拷贝、严格结果信封/输入hash/事件顺序/UTC秒级截止及安全上限。无写入、无原始载荷、无重试。

RED缺模块；首轮异步测试10项因未配置pytest-asyncio未执行，改为仓库已有asyncio.run方式后，新端口与原invoker30项全部通过（7条既有依赖警告）。命名invoker替身验证边界，不声称实际已安装新core。AR2-7扫描1880/分类168/迁移93，所有错误数组空；diff检查通过。memory-validate GREEN：1096 receipts/2691 events/1079 tasks，revision AOS-000573。

无主库/服务重启/部署/push。历史候选差异待新发布解决，真实首链未完成。后继三阶段消费的提交事务必须重验当前SourceOwner、策略/控制回执、安装和完整输入快照，才能写Occurrence。
