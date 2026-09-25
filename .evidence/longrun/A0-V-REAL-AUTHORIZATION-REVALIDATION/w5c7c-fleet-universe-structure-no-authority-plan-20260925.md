# W5c7c Fleet Universe 结构合同（永不授权）方案（2026-09-25）

上位 W5c7b：可信全机 universe 需要受管部署控制面签名、覆盖全部启动入口与旧入口禁止重启。当前无此来源，真实 DB 仍 `a0v_092`，任何自报布尔值或本机零观测不能成为 closure authority。

## 文件级九步

1. 复习 W5c7a/b、231/231-9、现有 Host topology/closure no-effect 分类器与 `a0v_093/094` 边界。
2. 本方案先提交。仅新增 `scripts/a0v_w5c7c_fleet_universe_structure.py` 纯结构分类器、`services/aos-api/tests/extension_runtime/test_a0v_w5c7c_fleet_universe_structure.py` 合同测试和 verification；不接真实 Host/DB/closure。
3. 严格字段集、类型、唯一 machine/launch surface/identity、revision/有效期与禁止空 universe。拒绝 caller 自报的签名、覆盖或 `topologyComplete` 标志；所有结果固定 `automaticAction=false`、`topologyComplete=false`、`closureAuthorized=false`。即使结构完整，也只给 `STRUCTURE_ONLY_UNTRUSTED`，不得被正式门消费。
4. 负例覆盖缺字段、重复节点/入口/身份、过期/未来、未知字段、自报 authority；输入不可变、不读文件/网络/数据库、不触发副作用。
5. 专项与 W5c5k–z/W5c6a–z、Host/closure/JDBC 累计回归；测试 PG 用后停。
6. 浏览器只读 rev4 停用，不保存/运行/冲刷队列。
7. 方案/代码一致性复审：结构校验不是签名验证，更不证明覆盖性；真实迁移、Host cutover、Fresh Owner 门依旧缺。
8. verification 后 CAS 更新 docs/AOS 跨对话上下文与 Prime 独立记忆并读回。
9. 下一波 W5c7d：先方案，选择可信签名与资产清单交叉验证切片；若无可用权威源则仅隔离测试，真实 closure 仍 no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。
