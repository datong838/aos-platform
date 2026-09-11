# Ecommerce growth 1.5.0 Registry metadata compatibility 修正方案

日期：2026-09-12

## 首次 apply 发现

Registry successor 首次 apply 在 `create_version` 前被 `manifest metadata does not match the target bundle` 拒绝。只读对账证明 publisher、bundle id、kind 均一致，唯一差异是 `displayName`：现有 Registry bundle 与不可变 1.4.0 都是“电商增长方案包（W3：六数字同事生产 Profile Candidate）”，1.5.0 Candidate 被生成器改成了“电商增长方案包（经营参谋阶段评审 Runtime Candidate）”。

失败后 Registry 中 1.5.0 版本数仍为 0；只产生发布前数据库备份和仓外 v5 签名树，没有 Installation、Provider、外部发布或 `.env` 变更。执行器没有捕获 Registry 域异常而直接 traceback，这是第二个需修复的 fail-closed 可观测性缺口。

## 修正规则

1. `displayName` 是 Registry bundle 跨版本身份字段，1.5.0 必须继承 1.4.0 的稳定值；版本的新能力由 version、manifest runtime 声明与证据表达，不通过改 bundle 身份名称表达。
2. 修改单用途 Candidate 生成器并重新生成 1.5.0；继续要求 1.4.0 完整 tree hash 不变、1.5.0 backend exact 等于作者树、内部 bundleRef 为 1.5.0。
3. 原 OCI v1 build/qualification 与 v5 签名树全部保留为被拒历史，不能用于再次发布。基于修正后的提交生成独立 v2 build、qualification、Receipt 和 successor signed tree v5-v2。
4. successor 执行器把 Registry/签名/数据库域异常统一转成带 reasonCode 的 SAFE_BLOCKED Receipt；只有确认 Registry 1.5.0 仍不存在后，才允许使用 v2 输入重新 apply。
5. 新增 Registry identity 合同测试，明确 1.5.0 displayName 必须等于 1.4.0，防止生成器再次漂移。

## 修改范围

- `scripts/prepare_ecommerce_growth_1_5_candidate.py`
- `bundles/candidates/ecommerce/solution.ecommerce.growth/1.5.0/bundle.yaml`
- `services/aos-api/tests/extension_runtime/test_runnable_ecommerce_candidates.py`
- `scripts/a0v_ecommerce_growth_1_5_registry_successor.py`
- `services/aos-api/tests/extension_runtime/test_a0v_ecommerce_growth_1_5_registry_successor.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/`

## 退出条件

Candidate/旧版不可变/Registry identity 测试全绿；v2 OCI build 与 qualification 各一次成功；1.5.0 Registry apply 成功且 replay 零 mutation；1.4.0 Registry 与正负租户 Installation 计数不变；失败 v1 和成功 v2 的边界均落证据。
