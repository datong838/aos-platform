# Workshop 累计回归完整性验收

- 日期：2026-08-29
- 分支：`m1`
- 范围：开发种子复合键、运行时 relation readiness、历史 Bundle 1.3.0 / Candidate 1.4.0 版本归属
- 数据边界：仅一次性 `_ti4_test` 数据库；未写入 `org-org/dev-project`，未运行或重放 P01～P12，未触发外部效果

## 方案与实现一致性

1. `widget_catalog`、`theme` 种子使用 `(org_id, project_id, id)` 冲突键，未增加跨租户全局唯一约束。
2. disposable seed 在写子记录前建立 `dev-org/dev-project` 父作用域。
3. legacy Workshop store 先以 `to_regclass` 只读核验 relation；正向缓存绑定精确 DSN 与 relation，不跨数据库复用。
4. 不可变 `solution.ecommerce.growth@1.3.0` release snapshot 使用固定 tree hash 验收；持续演进的开发组合目录保留六数字同事发布器、Harness、知识冷启动和查询模板所需资产。
5. D2 开发组合安装循环继续执行 30 artifact 与必要后续资产门槛；Candidate 1.4.0 另行验证新增 exports，不把三种目录身份混为一个版本事实。

## 测试证据

- `test_workshop_phase1.py`：`33 passed`
- 发布快照/开发组合/Candidate 与 AIP 直接消费者专项：`137 passed`
- 独立数据库迁移 + D2 安装卸载重装：`8 passed`
- ecommerce / SourceReadiness / Workshop / Business Investigation 累计：`1268 passed`
- `python3 -m compileall -q services/aos-api/aos_api`：GREEN
- `git diff --check`：GREEN

## 自然时槽只读事实

- `P08-customer-lite-qyh` 于 `2026-08-29T01:00:09.034932+00:00` 由自然 Cron 启动并成功完成。
- 读取事实：源行 `54`、写入 `54`、`CustomerLite` 源/投影 `54/54`，隔离 canary `0/0`。
- 本轮没有手工运行或重放 P08；该事实只证明 CustomerLite 自然同步成功，不自动授予客户触达、Provider、发布或其他外部副作用权限。

## 结论

本轮关闭了跨数据库 readiness 误缓存与 Bundle 目录身份串线，并保留现有 AIP/Workshop 资产消费者；未降低租户、迁移、发布或外部副作用门。页面与真实数据的浏览器复验继续使用精确 API owner，不以本文件替代浏览器证据。
