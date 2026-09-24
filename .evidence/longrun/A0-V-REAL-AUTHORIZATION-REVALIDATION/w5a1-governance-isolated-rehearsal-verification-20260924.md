# W5a1 治理最小克隆演练验收（2026-09-24）

## 结论

**W5a1 隔离演练与治理行保全 GREEN；正式库尚未 apply。** 本波遵守 `w5a1-governance-isolated-rehearsal-plan-20260924.md`、`w5a-governance-renewal-plan-20260924.md` 与 `formal-text-model-plan.md`。冻结 planHash `41813b34c4ce092d3bddd81115169ac52ca1b644819e57e5b29e801fb27a1265` 没有变；未再次调用 Provider、未发起业务 Run、未运行 definition。

## 逐步证据

1. `pg_catalog` 只读盘点治理发布链与 FK；固定表白名单 20 张，仅 `twa_org/twa_workspace` 和 AIP Budget/Governance/Guard/Network/Provider/Price/Policy/Model/Route 的 `org-org/dev-project` 行。旧 Eval 历史、商城源表、流水源表均不导出。计划/CAS 只读核验与原 W5a 一致。
2. `scripts/a0v_w5a_governance_clone.py` 在固定新库 `aos_w5a_governance_20260924` 用 `pg_dump --schema-only` 建库，只复制上述 20 张表的精确正向租户行；迁移头 `a0v_091`。私有 `governance-clone/` 0700、schema/prepare 0600。克隆内 130 张 `ecommerce_%/pipeline_%` 表均为空；`sourceDataRowsCopied=0`。
3. 独立连接逐行比较 20/20 白名单表一致、canary=0；9 个治理 head hash 一致。克隆中 18 条相关 RLS policy、10 个启用的相关自定义 trigger、20/20 表对运行角色可读。初次比较因无序 SQL 返回顺序产生 4 张表假差异，改为规范排序后 20/20 一致；并非内容漂移。
4. 仅在隔离库用同一 planHash 执行一次正式 Owner apply：Budget rev13、Price rev12、RuntimePolicy rev13、Model rev12、Route rev12，双 EvalGate `passed`；结果 `providerCalls=0`、`businessRuns=0`。独立回读正式库仍为 Budget rev12、Price rev11、Policy rev12、Model/Route rev11，克隆结果没有越库。隔离结果文件已收紧为 0600。
5. 对正式库当前治理行单独执行 binary COPY 保全，固定 20 张白名单表、按精确租户过滤，文件全部 0600、目录 0700；`manifest.json` 含每表计数和 SHA-256，不含商城源数据。逐文件重算 SHA-256，并在克隆连接的临时表中 20/20 恢复，对照正式库原行逐行一致，`W5A1_GOVERNANCE_PRESERVATION_RESTORE_GREEN`。原主库 CAS 与准备证明一致。旧 Eval/Receipt 是 append-only，保全限于发布前会被更新的治理 head 与依赖 revision；正式发布的新 Eval/Receipt 必须以后续精确键只读对账，不作回滚承诺。

## 代码与验证

- `scripts/a0v_w5a_governance_clone.py`：固定库/租户/表白名单、schema-only 校验、单次建库、精确行复制、治理行保全，未知/已存在状态拒绝重做。
- `scripts/a0v_formal_text_model_renewal.py`：仅新增固定演练库名称到允许列表，不放宽 first-installer 对正式库的身份检查。
- `services/aos-api/tests/extension_runtime/test_a0v_w5a_governance_clone.py`：越界表、租户范围、已有状态与缺失前置证明的拒绝测试。与原续期单测合计 14 passed、7 个既有 warnings；`git diff --check` 通过。
- 首次执行器预检发现 `twa_org` 的键为 `id`，在状态目录和数据库均未建立时修正，才执行建库。保全初次预检被准备文件的旧无序 hash 判为漂移，当时仅有空保全目录、无数据文件；独立按旧顺序核验 9/9 原 hash 后修正兼容读回，移除空目录，再完成一次保全。两处均未越过未知提交边界。

## 退出边界与下一波

本波只证明治理依赖最小克隆的同计划演练及相关行保全，**不证明完整数据库克隆与商城业务可运行**。正式库预算仍过期，W5 `options()` 仍不放行；旧 DS selection/controls 已过期、binding 仍 fenced。下一波 W5a2 先做新鲜只读门禁：planHash/有效窗、主库五个 CAS、精确 receipt/双 Eval idempotency 键零冲突、canary 零、8080 健康与仓库干净；再在原 state 同一计划仅一次正式库 apply。任何未知提交边界先冻结并只读对账，绝不换计划重发。正式治理续期核验 GREEN 后才进入 W5b 的 DS settlement/新控制链。
