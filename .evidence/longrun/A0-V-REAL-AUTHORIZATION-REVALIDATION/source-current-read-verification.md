# 源列表当前回读验证

基线92eb5ae1。GET /v1/sources直接调用load_source_metadata，tenant单次SQL仅投影公开props键和数据库configuration_revision，不读取连接密码/secretRef，不依赖hydrate一次的旧cache；失败503不回退。保留公开响应白名单。

先专项复现旧cache路径失败（1 failed/7 passed），修复后8单元+1PG组合共9 passed。PG真实token更新后list读取当前revision，返回不含password/secretRef。git diff --check通过。测试未包括故障503专项或浏览器，不能扩大。旧启动/pytest警告保留。

查询不改变共享map，所以不会把公开投影覆盖到可执行配置缓存。当前其他数据OS接口缓存行为不变，后续按真实接入需要继续处理。测试无public数据写入、无上游/模型调用，未重载API，未push，230 L0挂起。向导与真实经营首链未完成。
