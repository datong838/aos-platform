# E17-s3l SkillBinding 来源准入：文件级方案

基线 `m1@608aab2e`、Authority `AOS-001182`、Task `W5CB4-E17-S3L-SKILL-BINDING-ISSUER-PROVENANCE-20261003`。上位231与231-9要求运行和审批绑定原签名/租户/版本；56与64要求已评测→发布→绑定用原 Registry/Receipt，不能由手改库补配置。接续569，真库 `a0v_135` 只读、Host/worker/Provider关闭。

## 已读事实与待证伪点

- `AipSkillRegistry.create_binding` 只接受同租户、当前 published Skill；`evaluate_binding` 用 `AipSkillBindingReadinessService` 复核发布事件、Gate、Route/Policy、预算和 capability；`update_binding(active)` 又在写前复算 snapshot。原路径有 `skill_binding.create/evaluate/update` Receipt。
- 当前 `aos_runtime` 对 `aip_skill_binding` 的 SELECT/INSERT/UPDATE 权限为 `t|t|t`（对当前库只读查询），迁移 `aip6_001` 允许直接写行；`bind1_001` 只约束字段形状。s3k 的 Plan 读门验证 available+snapshot+expiry，但尚未复核 Skill 发行源或 binding Receipt。RLS 是租户隔离，不能替代签发来源。
- 下一测试仅在 conftest 自动建/删的 `aos_test_*_ti4_test` 库，用 org-org/dev-project 直接插 `draft` Skill + active/available/fresh SkillBinding，能力 Binding 可用；这是**攻击负例**，不是合法发布。预期 Plan blocked、freeze Receipt0、head 不动、dev-org 只读0。先运行旧码 RED；若未 RED，不做代码更改。

## 最小修复候选与边界

若 RED 成立，优先在 `services/aos-api/aos_api/aip_production_contract_store.py:_responsibility_blockers` 同一事务读取点，只允许有原 `skill_binding.create/evaluate/update` applied Receipt 且精确当前 published Skill 的 Binding 覆盖职责；不得凭一条手插 active/ready 行通过。先核既有合法测试夹具与原 Receipt 语义，避免无意改变已批准/冻结 Plan；若要变更全局 DB ACL 或引入独立签发角色，须列为独立迁移波，先全备份/克隆演练，不能在当前真库迁移。只改文件级最小点及必要测试。

专项验证新负例、原 Plan/Binding 相邻回归与隔离租户/Receipt；适用时浏览器只读验禁入。代码复审需明确应用层 Receipt 校验防误接线，但持有 runtime DB 写权限者也可插 Receipt，因此它不是强密码学或独立角色签发证明。缺独立发行身份不得将当前 Plan 标为正式正向。当前实例无写、无重放/手工 Run、不启 Host。
