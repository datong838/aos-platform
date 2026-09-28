# W5CB4 E17-aa3a｜数据库 active BudgetRevision 直写禁入验证

## 本切片

- 方案：`w5cb4-e17aa3a-db-active-budget-deny-plan-20260928.md`。线性 `a0v_111` 给 `public.aip_budget_revision` 添加无普通角色豁免的 BEFORE INSERT 门；active 直写固定报 `BUDGET_ACTIVATION_CONSUMPTION_REQUIRED`，Draft 保持原通路。
- RED：新增 `test_aip_budget_active_db_gate_pg.py` 后，未加迁移时 `1 failed`（未抛禁入异常）；加迁移后 `1 passed`。测试连接仅使用 conftest 的可销毁 `aos_test_*_ti4_test` 数据库；当前真实库仍为 `a0v_110`。
- 旧 reader 测试：`_budget_test_fixture.py` 将历史 active 种子限制在精确可销毁库，检查 trigger 存在，再在同一事务中由测试库 owner 暂停 trigger、以 `aos_runtime` 插入、恢复 trigger；发生异常整笔事务回滚。`test_w7_08_media_finance_settlement.py` 的同类种子复用这个测试通道。正式迁移、运行 Store 和真实库都没有此豁免。

## 新鲜验证与限制

- `AOS_DOTENV_DISABLED=1 services/aos-api/.venv/bin/pytest -q services/aos-api/tests/aip/test_w7_08_media_finance_settlement.py services/aos-api/tests/aip/test_aip_budget_active_db_gate_pg.py services/aos-api/tests/aip/test_aip_budget_store.py services/aos-api/tests/aip/test_aip_model_governance_policy_store.py`：退出 0，`12 passed`。
- 扩大命令含 `test_current_configuration_sources_pg.py` 与 `test_ecommerce_content_review_pending_pg.py`：退出 1，`9 failed, 4 passed, 21 skipped`。一项 W7 财务旧种子被本切片修好；八项内容测试在 `_upgrade_test_clone_to_head` 处先断言 `a0v_106`，而当前 head 为 `a0v_111`。这个测试文件已有他人未提交改动，本切片未编辑。其断言也落后于本波前的 `a0v_110`，不能把这组失败计为本门禁的正向验证；后续须由该文件 owner 对齐版本与 active fixture 后重跑。
- `git diff --check`：退出 0。未迁移当前真实库；未启动 Host/worker/Provider、未写业务租户 active 预算、未读商城源、未重放 Run。

## 后续门

1. 独立迁移波：当日备份校验、完整克隆恢复、迁移与门禁复测、零执行窗口，才允许将当前权威卷 `a0v_110→a0v_111` 与最新 API/Web 一起重启。
2. E17-aa3b：设计并实现不可由运行角色伪造的一次性批准消费；外部费用/价格上界真源不齐时仍保持 active 正向禁入。
3. 对齐上述内容测试的固定 head 与可销毁库种子，重跑累计门；不覆盖该文件的未提交改动。
