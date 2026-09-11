# 阶段评审结构化 Eval 输入 hash 消息方案

日期：2026-09-12

基线：`d46ba850`

状态：APPROVED_FOR_IMPLEMENTATION（作者树后续 1.5.0；现装 1.4.0 不变）

## 阻断与目标

真实复合 authority reader 不能直接接线：旧 `_sources_and_eval` 在数据库事务中调用 Growth 包 `derive_structure_case`，违反已经落地的“事务一关闭后才 IPC”合同。为移除此阻断，在既有 review operation 增加第五种纯消息 `validate_structure_case`。宿主提供已由 Owner 读取的原 query、阶段和 Eval Suite 当前 case input hash；包内按现有 `structure_case_from_query` 派生并计算 canonical SHA-256，只在等于 expected hash 时返回该 hash。

## Rules

1. 消息必须恰好含 `kind/query/stage/expectedCaseInputHash`；stage 限三阶段，hash 为 64 位小写十六进制。
2. 包侧复用既有严格 query parser/structure validator；返回只含 `caseInputHash`，不得回传 query、Evidence 内容或派生 case。
3. host port、prepared 上限和 Owner 完整门同步从四门改为五门；五门 kind 必须唯一且齐全。
4. hash 不符、query 非法、未知/额外字段、旧 1.4.0 PermissionError、超时和取消均原样停止，零重试、零发布。
5. 只修改作者树和宿主协议，不构建 Candidate、不改 Registry/Installation/runtime binding、不调用真实 Provider、不写租户数据。

## 文件

- `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/__init__.py`
- `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/analyst_stage_review_runtime_operation.py`
- `services/aos-api/aos_api/ecommerce_analyst_stage_review_package_port.py`
- `services/aos-api/aos_api/ecommerce_analyst_stage_review_coordinator.py`
- `services/aos-api/aos_api/ecommerce_analyst_stage_review_owner_binding.py`
- `services/aos-api/tests/extension_runtime/test_analyst_stage_review_runtime_operation.py`
- `services/aos-api/tests/extension_runtime/test_analyst_stage_review_installed_port.py`
- `services/aos-api/tests/extension_runtime/test_analyst_stage_review_coordinator.py`
- `services/aos-api/tests/test_ecommerce_analyst_stage_review_owner_binding.py`
- 本 plan/files/verification 与 closure manifest。

## 验收与下一门

合法真实 prompt 的派生 hash exact 匹配；错误 hash 和严格 envelope 拒绝。五门 one-shot、coordinator 上限、Owner 完整性、旧四门与结构规则全回归。完成后下一波实现真实复合 authority reader，把原 query 和 Suite case hash 组成第五消息，彻底移除事务内包调用。
