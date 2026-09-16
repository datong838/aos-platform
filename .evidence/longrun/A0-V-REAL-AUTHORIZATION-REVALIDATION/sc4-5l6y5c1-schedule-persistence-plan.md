# Y5c1 调度配置持久确认

2026-09-16，基线 ceeb339e。先方案后编码；m1、不 push、无主库写入。

问题：wave_ext.create_schedule 先写缓存再调用 _persist_safe，后者吞掉一般持久异常。patch_schedule 更直接修改缓存原对象。写库失败可能返回成功或污染页面状态，不能用于真实配置登记。

范围：仅 services/aos-api/aos_api/routers/wave_ext.py 中创建/编辑两入口及新增专用 _persist_schedule_confirmed；新增 services/aos-api/tests/test_schedule_configuration_persistence.py。保留原租户核验、字段合同和 data_os_store.persist_schedule。先持久、后发布缓存；patch 先复制旧 dict。持久 ApiError 原样传递，其他异常返回固定 SCHEDULE_PERSISTENCE_UNCONFIRMED/503，不暴露异常文本。任一持久异常使该 scope 的 loaded 标记失效，下次 GET 强制原数据库重新水合；不自动重写、不把未知提交宣称已回滚。原缓存只保留此前值。不得修改全局 _persist_safe 或其他业务路径。

验证：真实 app 同路径首个 POST 路由必须是 wave_ext；纯函数隔离持久 seam 的失败不新增/覆盖缓存、编辑失败不污染原 dict、成功先持久后缓存、ApiError/租户边界保持、未知提交后 GET 强制水合。首轮 Red，最小实现 Green，加原恢复 API/租户写入回归。无 UI 改动，不以 mock 写库代替 Y5c2 实际登记读回。

## 验收结果

Red：原 create_schedule 在 persist_schedule 抛错后没有抛 ApiError（/tmp/aos-y5c1-red.log）。最小修复创建/编辑缓存发布顺序、失败固定503、加载标记失效。新增8项测试含实际 app 首个有效 POST 路由、未知提交后的原 GET 水合；加原 schedule recovery API 与真实隔离PG租户写入回归，32 passed / 6.50s（/tmp/aos-y5c1-final.log）。最初路由测试直接扫描顶层 app.routes 得到空列表，按项目既有 FastAPI lazy effective_candidates 遍历后确认实际路径；这是测试适配，无路由顺序修改。

方案一致：不改 _persist_safe 全局行为、不修改运行接口、不新增表，不重试未知写入。主服务尚未重载，因此真实 API 仍不能宣称包含此修复。Y5c2 前先完成受控配置服务重载方案/健康核验，旧 host 的实际运行应先盘点，不能与当前开发代码状态混淆；不启用新增 snapshot worker。
