# W5a 治理有效窗续期计划（2026-09-24）

## 背景、方案复习与目标

- W4 已以 `75cf603f` 核验为 GREEN；W5 现行 `options()` 因 budget policy rev12 于 2026-09-23T16:17:45.943129Z 过期而失败。12 条旧 selection 也已过期，不能靠旧 `controls.json/options.json` 接续。
- 复用已验证的 `a0v_exact_text_live_eval.py`（固定 `text-readiness-v2` 三条公开合成文本、每条单次原探针）和 `a0v_formal_text_model_renewal.py`（新 planHash、Owner CAS、EvalGate、回执）。上位方案为 `formal-text-model-plan.md` 与 W2 续期 verification；不修改额度、价格或旧证据时间。
- 本波仅恢复 `org-org/dev-project` 的 Budget/Price/RuntimePolicy/Model/Route 当前开发授权有效窗，不创建业务 Run、不读商城源、不启用 DS/definition、不触碰 `dev-org`。

## 固定新批次身份

- 新私有根目录：`/Users/ddt/work/projects/ai_agent/.aos-recovery-20260920/state/q-advisor-baseline/br-text-governance-renewal/20260924-w5a/`，预检确认不存在；旧 2026-09-23 state/evidence 永久保留。
- 固定 profile：`text-readiness-v2`；目标库仅 `aos_meta_head`。三 case 为 `instruction/source/missing`，每 case 最多一次真实 Provider 调用；失败、submitted、unknown 一律冻结，不换目录或 key 补发。
- 计划冻结与结果在本批次独立 state 文件；任何写库前先保全主库并确认 planHash/current heads。秘密不入命令参数、输出、证据或 Git。

## 串行步骤与门禁

1. 只读核对当前 Budget head/失效时间、Provider/Network 配置、`m1`、8080、旧 W5 未推进；运行固定评测不带 `--apply` 的预检模式（无外部调用），冻结精确批次路径。若身份、授权或目录漂移，停止。
2. 对新 evidence 目录运行 `a0v_exact_text_live_eval.py --apply --profile text-readiness-v2` 一次；逐条回读 journal 为 completed/healthy/contract_passed，providerCalls=3、businessMutationCount=0。任一 unresolved 不重试，走只读诊断。
3. 用新证据目录执行 `a0v_formal_text_model_renewal.py` 计划冻结（不带 `--apply`）；要求 outcome `TEXT_RENEWAL_PLAN_FROZEN`、providerCalls=0、databaseWrites=0；保全 plan.json/hash 与当前 head CAS。
4. 按正式工作流先在独立克隆演练同一冻结计划；若 clone 与主库 head 不一致，不把 clone 的结果当生产证明。主库写入前做数据库备份/校验。
5. 在原 state/planHash 上仅一次 `--apply`，要求 Budget/Price/RuntimePolicy/Model/Route 和双 EvalGate 的正式结果均可回读；未知提交边界只读查 Owner journal/heads，不换新 planHash 重发。
6. 新鲜只读 `options()` 必须不再报预算失效；记录其后可能出现的旧 config/selection 错误，不把治理续期冒充 DS 可执行。写 verification、测试与风险复核，提交 m1，不 push；下一波 W5b 才设计/执行 DS settlement、新配置和当前控制链。

若第 4 步克隆或备份能力当前不可用，停在已冻结计划，不越过主库 apply。所有新评测仅固定合成文本，禁止替换为商城内容或 mock。
