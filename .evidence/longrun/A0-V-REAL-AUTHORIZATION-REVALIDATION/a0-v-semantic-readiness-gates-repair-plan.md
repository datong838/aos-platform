# A0-V 语义就绪门修复方案

## 1. 缺口

`a0-v-readiness-collector.py` 当前能验证 HTTP 状态、空集合和基础租户声明，但对 HTTP 200 正文的业务就绪语义检查不足。迁移修复后，canonical SourceReadiness 返回 200 且 `status=blocked`，采集器却移除了该 gate 的 blocker；Agent/Capability/Model 集合未来只要出现任意记录，也可能绕过数量、可运行状态、健康有效期和预算状态要求，形成假 GREEN。

该缺口阻止 A0-V 的验收动作 A0-02/A0-06，也会使 A1 在缺真实数据、不可运行 Agent 或过期模型健康时错误入场。

## 2. 最小文件改动

- 修改 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/a0-v-readiness-collector.py`；
- 修改 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/verify_a0_v.py`；
- 新增 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/test_a0_v_readiness_collector.py`；
- 重采 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/a0-v-readiness-result.json`；
- 新增对应验证记录。

不修改业务 API、数据库 schema、运行配置或任何租户记录。

## 3. 语义门

1. canonical 与 Workshop SourceReadiness 只有 `status=ready`、12 个来源且每项 `status=ready` 才通过；其他状态保留可解释 blocker。
2. Agent catalog 必须精确包含 6 个定义、37 个 Skill 定义、10 个 Capability 定义、6 个已安装实例和 6 个 runnable 实例；runtime readiness 的 6 个 catalog item 必须均为 runnable 且 blockers 为空。
3. Capability catalog 必须精确包含 10 项且 10 项 available。
4. Model runtime 除必要集合非空外，至少一个 route resolution 必须 `readiness=ready`；至少一个当前 Provider health 必须 `status=healthy` 且 `expiresAt > generatedAt`。
5. Model chain 至少一条链，且首链全部 node 为 ready、无 blockerCode。
6. Model cost 至少一个 `status=active`、CNY、`hardStop=true`、日/月额度均为正数的预算。
7. 任一响应形状缺失或类型错误均按 `MALFORMED_READINESS_BODY` 失败关闭，不能抛出采集器异常或默认为空值通过。

现阶段生产合同集合仍只检查非空；在准备写入该类配置前，须读取其 exact-current 契约并补齐对应语义门，不能依靠“有一条记录”进入 A1。

## 4. 验证与退出

专项测试用纯内存 HTTP fixture 覆盖 ready、blocked、过期健康、数量不足、畸形正文和 canary，不访问数据库或网络。当前恢复环境重采后，SourceReadiness 仍必须以 `STATUS_BLOCKED` 留在 blocker 列表；其余 16 项不得无故减少。

退出标记为 `A0V_SEMANTIC_READINESS_GATES_GREEN`，它只表示证据判定器可靠，不表示 A0-V 或任何真实业务场景 GREEN。
