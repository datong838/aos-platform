# AR2-7D 描述回执恢复切片验证

日期：2026-09-08。主线 m1；本记录仅覆盖 D1 描述服务修复，不推进整波 GREEN。

- 代码：`65758763`（基线 `1e7b57db`）；方案：docs `cfc57c9`。
- 结果：隔日同幂等键返回首次快照；回执绑定原命令；缺字段、JSON null、错误 UUID、伪造请求／内容哈希被拒绝，失败不占住幂等键；跨租户读取不可见；并发首次写入唯一。
- 实测：`AOS_EXTENSION_PG_TEST=1 PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/extension_runtime/test_investigation_description_store_pg.py services/aos-api/tests/extension_runtime/test_ecommerce_growth_runtime_adapters.py services/aos-api/tests/test_source_readiness_source.py`：28 passed，5.62s；7 条既有框架警告。
- Prime：`prime_description_recovery` 独立只读复审 PASS；审查指出的首尾空白哈希分歧已由严格输入校验和参数化反例关闭。
- 数据边界：仅一次性 PostgreSQL 测试库；没有共享库迁移、真实业务变更、模型调用或外部发布。无前端改动，不制造浏览器验收结论。
- 当前仍为 AR2-7D 第3/8步。下一施工切片：DataFulfillHostService 的需求请求与履约绑定，先补精确政策参数和完整回读合同，再实现同事务宿主接线。
