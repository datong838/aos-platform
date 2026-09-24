# W5a 治理续期部分验收与冻结边界（2026-09-24）

## 结论

**停在计划冻结，未发布。** 依据 `w5a-governance-renewal-plan-20260924.md`，步骤 1–3 完成；步骤 4 的当前态独立克隆未具备无商城数据读取的受控路径，因此步骤 5 主库 apply 和步骤 6 续期验收均未执行。主库 budget head 独立回读仍为 rev12，旧有效期 2026-09-23T16:17:45.943129Z；不得将候选 rev13 报为生效。

## 已完成证据

- 新私有批次：`.aos-recovery-20260920/state/q-advisor-baseline/br-text-governance-renewal/20260924-w5a/`；旧 09-23 证据未覆盖。
- 固定 `text-readiness-v2` 预检：instruction/source/missing，Provider 调用 0；Provider rev1 与 Network rev1 均 active，Network 有效至 2027-09-10。
- 正式合成文本评测一次：`FIXED_TEXT_CASES_PASSED`，3 次 Provider 调用、业务变更 0；三 case 均 completed/healthy/response_contract_passed，journal 0600，观察时间 2026-09-24T02:52:33–35Z；无商城输入与回答正文留证。
- 计划冻结：`TEXT_RENEWAL_PLAN_FROZEN`，planHash `41813b34c4ce092d3bddd81115169ac52ca1b644819e57e5b29e801fb27a1265`；providerCalls=0、databaseWrites=0。候选 budget rev13、候选窗口 2026-09-24T02:53:28.637050Z 至 2026-09-25T02:52:33.666717Z。`plan.json` 为 0600。
- 续期负向单测 7 passed/7 warnings；主库再次回读 rev12，证明没有因计划冻结偷偷推进 head。

## 阻断与下一波

- 可连接的旧 `aos_text_renewal_20260912` 克隆并非当前 rev12 基线，不能用它证明当前计划的 CAS/Owner 路径。现有通用全库备份/恢复会触及商城数据，与“不得读取商城源数据”冲突；不应以测试绿替代当前态演练。
- 下一波先制定并验证**治理依赖最小克隆**：仅带必要 AIP Provider/Network/Quota/Budget/Price/Policy/Model/Route/Eval/租户权威行，明确 FK/角色/迁移头与敏感列边界；不导出商城表、对象、订单或客户数据。用冻结的同一 planHash 在该克隆演练并回读，再另行决定主库保全和一次 apply。若无法证明完整依赖闭包，保持本波冻结，不改变旧 state、不重打三次 Provider 调用。
- W5 旧 controls/options 仍过期，DS binding 仍 fenced；自然 dispatch 未恢复，不手工 `run_definition`。
