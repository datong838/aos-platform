# W5c6n 组合测试环境顺序与 skip 可验证性方案（2026-09-25）

上位 W5c6m 已确认真实 closure 缺全机拓扑权威来源；本波转向独立测试债，不推进真实 Store/Owner/Host 效应。`services/aos-api/tests/conftest.py` 的 session fixture 建立一次性 PG 并设置 `AOS_DATABASE_URL`；部分旧测试在函数 fixture 中整体替换 `os.environ` 或在配置函数中移除该键，存在跨模块顺序风险。先复现、辨明，而非先改共享 fixture。

## 文件级九步

1. 复习 A0-V no-effect 上位边界、测试 bootstrap 与相关旧测试；记录可重现的文件组合和报错/skip。
2. 本方案先提交。候选最小文件仅限已定位的测试模块和对应回归合同；若根因不在候选范围，先修订本方案再编码。生产代码、真实数据库、部署不改。
3. 以隔离 `aos_test_*_ti4_test` 数据库复现正反顺序；明确 `AOS_DATABASE_URL` 身份必须在 session 生命周期稳定。不得用真实 aos_meta 作为试验库。
4. 对确定的函数级环境污染做最小修复；保留被测 Host/配置逻辑要求清除继承凭据的原断言，避免改变安全合同。`skip` 只限确实缺外部 PG，断言/代码失败不得伪装为 skip。
5. 专项正反顺序、原模块、W5c5k–W5c6m 累计回归；记录 passed/skipped 和精确原因。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列；UI 证据不替代 DB。
7. 复审方案/代码/测试一致性、共享 fixture 生命周期、真实权限边界，保留未解决债。
8. verification 文件提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立记忆并读回。
9. 下一波按真实复现结果处理剩余旧 skip/测试债，或等待正式 closure 新权威来源；先计划再实现。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。
