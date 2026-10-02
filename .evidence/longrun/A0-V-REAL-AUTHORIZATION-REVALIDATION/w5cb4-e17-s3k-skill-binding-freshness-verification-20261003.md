# E17-s3k SkillBinding 新鲜度准入：RED、最小实现与复核

基线 `m1@c0967688`、Authority `AOS-001181`；文件级方案 `w5cb4-e17-s3k-skill-binding-freshness-plan-20261003.md` 先于代码。只改 `aip_production_contract_store.py:_responsibility_blockers` 及 `test_w2b_production_contract_store.py`；无迁移、无真实库写、无 Provider/Host 动作。

## RED → GREEN

- 新测试在自动创建/销毁的独立 PostgreSQL 库、`org-org/dev-project` 以直接 active SkillBinding **仅作负例攻击输入**，CapabilityBinding 保持 healthy/available/fresh；两组分别为 SkillBinding `readiness=unknown` 和 `available` 但已过期。旧代码首例 `created.readiness=READY`，预期 BLOCKED，pytest exit1；证明 Plan 创建误判 ready，**未在旧码上进一步执行实际 freeze 越权**。
- 最小修复在同一读取点先筛 active 且 `readiness=available`、snapshot 非空、expiry>检查时刻的 SkillBinding；无 active 继续原 `SKILL_BINDING_NOT_ACTIVE`，active 但不就绪为 `SKILL_BINDING_NOT_READY`，过期为 `SKILL_BINDING_STALE`。只有筛过的 Binding 才能贡献 CapabilityBinding 引用；后续 capability health/operational/fresh 原检查保留。负例两组 `2 passed/7 warnings`、exit0；两者 `freeze` 拒绝、freeze Receipt0、Plan head 不动；同测试对 dev-org 的该 Plan ID 只读 count0。
- 新测试最初误用请求键为 Plan ID、dict row 数值索引和非唯一测试 Logic ID，均先修正测试夹具，再得以上生产修复结论；这些是测试编排错误，不计为生产 RED。无关服务行为未借测试错误修补。

## 相邻与页面

| 检查 | 新鲜结果 |
|---|---|
| `test_w2b_production_contract_store.py` + `test_aip_skill_binding_readiness_service.py` | 20 passed/7 warnings，exit0 |
| 单独 `test_aip_agent_registry_store.py` | 5 passed/7 warnings，exit0 |
| 新两负例 + `test_ecommerce_business_investigation_aip_authority.py` | 36 passed/7 warnings，exit0 |
| 新负例最后一次重验 | 2 passed/7 warnings，exit0 |
| `py_compile`、目标 `git diff --check` | 均 exit0 |

三文件一次合跑曾 6 failed：四项为旧测试直插未评测 active Binding 或轻量 fake connection 没给新列，已按原测试意图补 ready/fresh 夹具；另外两项是同 session 的 dev-org fixture 污染 AgentRegistry 的“canary 空”前提，单独运行原 Registry 5 passed。该次失败保留，不用分开运行掩盖生产回归；相邻检验按独立库边界分别执行。

浏览器现有 8434 `/aip/skill-publish` 只读回 org-org/dev-project、37已评测/0已发布、三项正式来源 blocker、发布按钮 disabled、电商无可见入口；截图与 AX 在本轮 CUA 工具记录。页面/API 进程仍是此提交前版本，本波浏览器只证明当前预览禁入状态，**不是新服务端门已在线生效**。签名 Growth 全栈测试缺显式 disposable PG/OCI/签名 Receipt，本轮不运行也不计通过。

## 方案一致性与剩余风险

实现只缩紧 Plan create/revise/freeze 的共用职责读取门，不改原 SkillBinding Store、Capability 读证和现有正式身份准入。原 Route/Model Eval/签名 Skill/六 Binding、当前八配置、Host Owner、自然首链仍缺。直接能写 SkillBinding 表的角色理论上仍可伪造 `available` 与 snapshot；本波只证明“active、未知或过期”失败封闭，不能把它外推为数据库级签发来源认证。下波应对 active+伪造 ready 的发行/评测来源做独立 RED，再决定数据库写门或受限 issuer 接线；不得仅靠当前状态列开放 Plan 正向。
