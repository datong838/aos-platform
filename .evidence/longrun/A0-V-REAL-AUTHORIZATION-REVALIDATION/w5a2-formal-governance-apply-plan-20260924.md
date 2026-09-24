# W5a2 正式治理续期一次发布计划（2026-09-24）

## 前置权威

W5a1 验收 `d0ff4cc0`：固定 planHash `41813b34c4ce092d3bddd81115169ac52ca1b644819e57e5b29e801fb27a1265`，最小治理克隆同计划 Owner 发布和双 EvalGate 通过，正式库治理行 20 表私有保全并临时表恢复 20/20。复习上位 `formal-text-model-plan.md` 与 W5a 原计划。本波仅 `org-org/dev-project` 正式治理续期；不启用安装/definition、不读商城源、不手工 `run_definition`。

## 串行步骤

1. 只读核对 m1 HEAD/干净、8080 健康、W5a 固定计划/原证据、有效窗、Provider/Network 当前 active、主库 Budget/Price/Policy/Model/Route 五个 CAS 与克隆演练之前完全一致。保全文件逐 SHA-256，canary 零。
2. 只读核对该 planHash 派生 Budget/Price/Policy/Model/Route 五个 Owner 幂等键在主库均不存在；Model candidate 的精确 Eval run 键和两 Gate 稳定 ID 不存在。Route candidate hash 含主库本次 Model Gate 的正式 hash（含决定时间），不能拿克隆 Route Eval 键冒充主库将来的精确键；主库 Route 键须在发布链生成后由 `_derive` 按既有 report/target/hash 规则自行校验并在步骤 4 回读。任一已知键存在或未知，冻结并只读对账，绝不复发。
3. 仅在原 W5a state、原 evidenceDir、原 planHash 下对 `aos_meta_head` 执行 `a0v_formal_text_model_renewal.py --apply` **一次**；输出新私有结果文件 0600。脚本可能跨多个 Owner 事务，错误/中断后禁止重新执行本步骤，先核对每个 receipt/head/run/report/gate 及已写边界。
4. 独立只读回读 Budget rev13、Price rev12、Policy rev13、Model/Route rev12、双正式 EvalGate passed、Owner receipt 键唯一、Provider 调用 0、业务 Run/Store Receipt/ecom_link 零、canary 零；新鲜 W5 `options()` 不再因 budget 过期失败。不得把治理续期当作 DS 解围。
5. 测试与风险审查：续期单测、隔离克隆测试、计划与真实结果一致性；写 W5a2 verification，提交 m1，不 push。下一波 W5b 才处理旧 selection/controls 到期、DS binding fenced 与重建当前定义的受控链。

## 停止条件

任何主库写入结果不明、计划/租户/幂等键漂移、证据失效或未保存执行结果，先冻结与只读对账；不自动重试、不生成新 planHash、不再调用 Provider。`dev-org/dev-project` 永不作为正向租户。
