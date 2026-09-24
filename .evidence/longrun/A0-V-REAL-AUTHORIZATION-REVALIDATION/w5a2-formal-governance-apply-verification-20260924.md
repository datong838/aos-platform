# W5a2 正式治理续期验收（2026-09-24）

## 结论

**正式治理续期 GREEN；DS 调度仍冻结。** 按 `w5a2-formal-governance-apply-plan-20260924.md`，对 `aos_meta_head`、`org-org/dev-project`、W5a 原目录与原 planHash `41813b34c4ce092d3bddd81115169ac52ca1b644819e57e5b29e801fb27a1265` 只执行一次 `--apply`。未重打 Provider 评测、未发起业务 Run、未启用定义或安装，不读商城源数据。

## 门禁与独立回读

1. 写前：m1 干净、8080 `/v1/health` 可达，原三条固定 `text-readiness-v2` 证据当前可核验，计划有效期至 2026-09-25T02:52:33.666717Z。W5a1 私有 20 表保全每文件 SHA-256 和 0600 均再次核验；五个正式库 CAS 为 Budget/Policy rev12、Price/Model/Route rev11。五个 Owner 幂等键、精确 Model Eval 键及稳定 Gate ID 在正式库均为 0，canary 为 0。
2. 执行：`a0v_formal_text_model_renewal.py` 在原计划下对正式库一次返回完整结果，`providerCalls=0`、`businessRuns=0`，结果文件已改为 0600。正式 Model hash `f3bb08836758f194023bde3eecde8890f00192704e08897ed368a40928dd0a73`，Route hash `f9628f91d6a161eef844e2e933322adcbcdca3abcaa72f5c18e1f8c1ec82ddfd`；与克隆 hash 不同符合 Gate 决定时间参与 hash 的方案，不是漂移。
3. 独立数据库回读：Budget rev13/version13，Price rev12/version12，RuntimePolicy rev13/version13，Model rev12/version12，Route rev12/version12；同 planHash 下 Budget Owner receipt 1、Runtime Owner receipt 4。Model/Route 两条 Eval Run 均 `succeeded`，两正式 Gate 均 `passed`，canary=0。Budget rev13 有效至 2026-09-25T02:52:33.666717Z；模型/路由不是永续授权。
4. 对 W5 DS `options()` 仅调用服务只读方法，现不再报预算过期，而报 `runtime policy reference is not current and exact`。旧安装配置/选择仍引用旧策略，binding 仍 fenced；这不属于 W5a2 放行范围。没有调用带落盘副作用的旧 `options` CLI，也没有复用其过期 frozen 文件。
5. 续期与克隆单测合计 14 passed、7 个既有 warnings；`git diff --check` 通过。原 `formal-text-model-plan.md` 的 Owner/Eval/回执边界与实际一致。风险：发布链跨多个事务，但本次有完整结果和精确回读；以后若未知结果仍按原计划只读对账，不得以本次 GREEN 授权重放。

## 下一波 W5b

先写方案，聚焦 DS 已释放 Owner settlement、当前 Policy rev13 的配置重建、12 条旧 selection 到期与旧 controls/options 不可复用。仍需先核对旧 DR-bound definition disabled、DS binding fenced、attempt/Receipt 基线、Cron/worker 状态；按正式 Owner API 生成新控制链并独立回读，之后才考虑退役旧定义、配置/启用新定义。任何未知提交边界不补发，不手工 `run_definition`。
