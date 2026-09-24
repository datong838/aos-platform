# W5c4x stalled Owner 隔离事务门禁测试方案（2026-09-25）

上位 231 A0-V、231-9 BG-00，前置 W5c4w 静态请求/SQL 合同 184 passed；真实原组未过严格 24h。W3 部署 `a0v_091` 后尚无事务级专测。本波只在 pytest 自动创建/销毁的隔离 PG 验证正式函数**拒绝侧**，不调用真实组、不修改生产数据。完整 12 Run 成功路径 fixture 如不能在本波可靠构造，不伪称覆盖。

## 文件级九步

1. 复习 `a0v_091` SQL、`StalledSnapshotGroupClosureService`、隔离测试 `conftest.py`、231 A0-V 及 W5c4t 的时间门。
2. 文件清单：本方案；新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c4x_stalled_owner_pg.py`；本波 verification。不得改迁移/Owner/真实 group。
3. 最小实现：隔离数据库调用函数，核缺少 maintainer/SERIALIZABLE 时立即 42501、维护角色下缺少当前 admin/owner 时 42501、无原始 claim 时拒绝且 receipt=0；如可信 fixture 可完整构造，再补 12 Run 成功与 replay，否则登记缺口进入下一波。
4. 专项测试先跑 RED/环境定位，再 GREEN；只以 SQLSTATE 和隔离库 receipt 读回作结论。
5. 累计回归 W5c3/W5c4、attempt/lease、静态合同与事务拒绝；慢集有界，不以中断部分冒充全绿。
6. 浏览器只读核 12 计划与整组入口，不触发业务执行。
7. 一致性复审：拒绝侧通过不等于成功侧、真实组关闭或授权；严格 24h 和唯一 key、effect evidence 不改。
8. verification 提交后 CAS 更新 AOS 上下文及 Prime 独立受管记忆、读回。
9. 下一波 W5c4y：若本波未覆盖，构造完整 12 Run fixture 验成功/回滚/重放；真实组过严格 24h 后另起正式关闭方案并用原 Owner 一次调用。

任何真实 attempt/Receipt/定义漂移先冻结，禁止旧代补跑、商城源行读取、push。
