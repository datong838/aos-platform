# W5c9o｜路由清单 547→550 测试基线差异审计与最小修正

## 上位/现状

W5c9n `m1@85660c55`/AOS-000702：Dataset 文档专项 GREEN、累计旧 `test_domain_router_manifest.py` 硬编码 547 但当前 manifest 550，故累计 RED。231 要求真差异先查来源再修，不能盲改断言。运行中的 18181 旧代码、8080 离线；原组 no-authority 不变。

## 文件级清单与安全门

- 只读检查 `services/aos-api/aos_api/routers/domain_manifest.json`、`domain_aggregates.py`、`scripts/generate_domain_aggregates.py`、`services/aos-api/tests/test_domain_router_manifest.py`；用当前 Git 历史定位多出的三项提交与域分布，核对 `order` 连续、(module,attribute) 唯一、生成器 `--check` 一致。不能凭总数直接重写生产 manifest。
- 如果三项是已提交的受控注册，**只**修 `test_domain_router_manifest.py` 的陈旧常量/域计数/哈希期望；优先从冻结的当前清单精确得到常量，保留唯一键和顺序负例，不把断言改成 `len(manifest)` 同义反复。若来源/归属不明，停止于 UNKNOWN，不编码。
- 测试必须 `--noconftest` 避免全局 PG 迁移夹具；先 RED 当前测试，最小修后专项与受影响累计（包含 W5c9n 文档测试、路由 precedence 的安全子集），不进入 app lifespan 或触发业务 handler。浏览器 8080 离线。
- audit/verification、m1、D-waves/AOS CAS/Prime。后续继续其余文档冲突切片，但任何业务真实 ACK/closure 权威不变。

## 九步

1. 复习 231、W5c9n 与 manifest 冻结合同。
2. 本计划先提交。
3. 精确差异/历史/生成器只读核对。
4. 来源受控时最小测试基线修正。
5. 专项/累计 `--noconftest`。
6. 方案/代码/唯一键/顺序/兼容复审。
7. 8080 业务浏览器离线。
8. audit/verification、精确提交、D-waves/AOS CAS/Prime。
9. 自动下一波继续下一组 OpenAPI 冲突文档修复或独立安全债。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
