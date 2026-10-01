# BG00GI verification（2026-10-01）

## 基线与复审

AOS-001049 / m1@56274293；开工 memory-status 七强一致CURRENT，memory-validate GREEN（1504 Delivery/1502 Task/3998 events）。m1单写；既有browser脚本、pnpm-lock、旧证据和test-only文件未纳入本波。

对照231-5、225、P2g30b与442：预算上限是首生/返工共同字段，不能单独判定RETURN。源代码仅新增_REPAIR_MARKERS（六字段减budgetUpperBoundMinor）并替换两处识别；_REPAIR_KEYS精确合同、RETURN当前权威禁入、风险策略、预算Store没有修改。不涉及迁移与前端，browser不适用。

## RED→GREEN

首次测试收集因canonical_hash导入位置错误exit2，已修到既有reservation_store定义；不是业务RED。随后运行：

```sh
cd services/aos-api
.venv/bin/python -m pytest -q tests/extension_runtime/test_ecommerce_content_repair_action_binding.py tests/aip/test_content_first_action_budget_pg.py --tb=short --show-capture=no
```

实现前 `/tmp/aos-gi-red.log`：exit1，3 failed/9 passed/5.82s。R1首生REPAIR_ACTION_EXECUTABLE_REVIEW_REQUIRED、R2及真实Store首生REPAIR_ACTION_EXACT_PAYLOAD_REQUIRED。
实现后 `/tmp/aos-gi-focused.log`：exit0，12 passed/5.30s，7已有warnings。

累计命令（`/tmp/aos-gi-regression.log`）：

```sh
.venv/bin/python -m pytest -q \
 tests/extension_runtime/test_ecommerce_content_repair_action_binding.py \
 tests/aip/test_content_first_action_budget_pg.py \
 tests/extension_runtime/test_ecommerce_content_repair_approval_authority.py \
 tests/extension_runtime/test_ecommerce_content_repair_brief_authority.py \
 tests/extension_runtime/test_ecommerce_content_budget_command_owner.py \
 tests/extension_runtime/test_ecommerce_content_budget_task_ref.py \
 tests/aip/test_budget_configuration_runtime_pg.py \
 tests/aip/test_budget_cost_configuration_pg.py \
 tests/aip/test_budget_cost_consumer_pg.py --tb=short --show-capture=no
```

exit0：64 passed/36.06s，7已有warnings。三文件compileall及精确git diff --check exit0。

## 联合PG实际覆盖与边界

- 标准conftest创建完整迁移aos_test_*_ti4_test库；费用批准使用已有TLS签名issuer、低权限消费和GE配置派生。Provider与身份前置属于隔离测试依赖，不是正式实例授权。
- TaskStore创建Task、Plan、批准、Run并start；ActionStore create_proposal→不同checker decide，重复调用同一key返回同一结果；maker自批拒绝。无INSERT审批、无固定action_binding_hash、无静态active价格、无关闭guard。
- 首生仅带budgetUpperBoundMinor不误判RETURN；R1不提升risk。五个其他识别字段任一与金额组合仍拒绝，六字段RETURN仍因缺current producer禁入，遗留RETURN checker仍拒。
- 获批Action无ImpactPreview/binding时，完整reserve依次读GE Budget/Price及当前Task/Run后，在真实_approval_authority拒绝，按invocation_key回读reservation=0。不能据此宣称成功held/Provider/自然首链。
- 隔离ActionType snapshot和checker字符串是Store级测试输入，尚未证明HTTP元数据/身份生产链；无商城源/外部效果/旧12Run/手工run_definition。真实库未连接、迁移或重启。

## 下一步必须解决

BG00GJ：ContentBudgetCommandOwner._minimum_bound_fen对development_cost_authorization直接拒绝，GE派生风险价无法进入自然内容Owner。先补文件级方案，复用require_cost_risk同事务当前批准/Provider/额度门接线，保持数字价格原路径；真PG派生源正负及撤销/并发/金额上限测试，不能填零价格。仍须独立解决当前frozen ImpactPreview与正式Action绑定，以及Model Quota/Eval合法来源。正式实例切换须独立备份恢复/克隆全链/零窗口；自然首链、八场景、观察发布未完成。
