# AR2-7D D1 当前规范库全集读取验证

- 恢复基线 m1@fa0612c5、AOS-000571；2026-09-09，沿用原 ACTIVE Task/Lease。方案见同目录 ar2-7d-canonical-population-plan.md 和 231-6 已有施工卡。
- 接续上次遗留 Red 测试，首次确认 ModuleNotFoundError；新增 CanonicalPopulationReader 后专项/选择邻接纯单测 **36 passed, 6 warnings in 7.34s**，宿主适配/查询测量/质量邻接 **49 passed, 7 warnings in 7.69s**。
- 默认 pytest 启动钩子连接 5433 被拒绝，21 项 setup error 不计通过；改用 `--noconftest` 只运行这五份明确无数据库依赖的纯测试。没有修改端点角色、启动共享库或对真实租户写入。PostgreSQL 并发/真实 SQL 尚未验，不能用内存连接测试替代。
- 覆盖稳定事务隔离、当前三选择引用、完整物理范围、99/100 上限、空集合、重复身份、分隔符身份、类型/哈希/时间非法值、旧来源时间原样保留；不返回 properties，不产出质量结论、不接 DataFulfill 注册。
- 独立只读审查未发现阻断缺陷；审查实现 SHA256=5dcca4b648e1947c3fe1537f616cb849e370be920fcc648daf1e0e3bb751774e，测试 SHA256=3915e770990f79ed0e0024a49ba930dc2493c91aa53c7bedadb9b95acd5af962。审查并非外部 Prime 服务回读，不制造 Prime PASS 记录。
- 闭包清册修复裸 source 路径歧义，登记此前新增编排节点与本次 Data 读取者。`verify_closure.py --phase ar2-1`：扫描1694、分类85、迁移57；hash/正向/反向/跨层/动态错误全部为空。沿用 ar2-1 旧入口保持合同，**不声称 ar2-7 最终切换通过**。
- `git diff --check` GREEN。测试退出日志包含既有 JDBC cleanup closed-stream 错误；pytest 退出码为0，未改与本切片无关的日志实现。
- 下一项：核实 ecom_ingest_receipt 与具体对象版本之间可证明的采集关系，补独立采集依据及固定业务窗口/规则；source_updated_at 仍不得冒充采集时间。完整 7D D1～D4、7E 与 AR2 首链未完成。
