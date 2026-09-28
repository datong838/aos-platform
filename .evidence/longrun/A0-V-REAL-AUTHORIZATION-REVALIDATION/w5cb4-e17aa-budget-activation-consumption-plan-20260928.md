# W5CB4 E17-aa｜预算批准消费与所有发布者禁入文件级方案

## 上位方案与当前事实

复习 231-3/5/9：预算按当前 Head、费用账户/期间/币种与上界核验；批准绑定精确条款及当前 maker/checker，执行前再次查撤销/过期；同事务单次消费及 Receipt，未知费用不当 0。`m1@4f122d69`、当前库 `a0v_110`、`org-org/dev-project` 仅一名正式 owner，预算 Head/Revision/四张 activation 证据表均 0；不能执行真实正向激活。E17-y2 的 `externalUsageProven=false` 与 `activationEligible=false` 是正式阻断，不得由客户端改写。

调用点审计发现 `AipBudgetAuthorityStore.publish` 仍允许 Python 内部传 `lifecycle=active`；HTTP active 422 仅挡 API。现有 `scripts/a0v_current_runtime_configuration_authority.py` 指向旧库且使用历史批准显示文本，`scripts/aip/bootstrap_r1_runtime_authority.py` 是历史初始化路径；两个入口不能作为当前正式审批。`aip_model_runtime` 等以 budget Store 读取为主。先用测试固定“所有当前发布者不得绕过消费者”的边界，避免当前库迁移后误将预览批准当激活权。

## 串行实施

1. **E17-aa1 内部入口守卫**：先在 `services/aos-api/tests/aip/test_aip_budget_store.py` 加 RED：公开 `publish` 的 active 新建/换版均拒绝且不写 Head/Revision/Receipt，历史隔离测试用途需具名适配；在 `services/aos-api/aos_api/aip_budget_store.py` 做最小失败封闭。审查 `aip_model_governance_policy_store`、`aip7` 等旧测试的目的，不删除其负例或把 test mock 当正式权限。旧初始化脚本继续精确拒绝当前库，不拓宽其来源。专项与相邻回归后收口。
2. **E17-aa2 正式用量证据**：先确定当前可信内部账本、价格版本、计量上界与外部账单权威引用。仅以 AOS 空账本不足以证明外部费用；没有可信来源时继续 `externalUsageProven=false`，不可加用户可自报布尔值或测试值。若有正式来源，追加不可变证据和验过期/币种/期间/价格/unknown 的 PG 负例，先方案/迁移安全波再落库。
3. **E17-aa3 原子消费**：只从当前 scoped 事务读取 preview/approved decision/未撤销/未消费/两名当前正式成员、当前 Draft Head 和费用证据；锁 Head 与单次消费键，同事务写 active BudgetRevision、唯一消费 Receipt，重复键精确重读、漂移 409。任何条件缺失保持公开 active 422、Host 0。当前租户无第二正式成员，真实正向验收只能等待正式权限来源，不能在当前库造人。

## 文件边界、退出与风险

aa1 仅改预算 Store 与对应测试，可能涉及需明确改为 Draft fixture 的邻接测试；代码改动前先 RED。aa2/aa3 需另列数据库迁移、合同、Store、路由与隔离 PG 测试，不能把三个切片一口气绕开真实用量门。任何代码迁移高于当前 `a0v_110` 时，当前 API/卷继续按独立安全波切换。每个切片须 verification、D-waves、上下文/Prime 和 m1 精确提交，随后立即进入下一切片；不 push、不读商城源、不启 Host/worker、不碰旧 12 Run/230 L0。
