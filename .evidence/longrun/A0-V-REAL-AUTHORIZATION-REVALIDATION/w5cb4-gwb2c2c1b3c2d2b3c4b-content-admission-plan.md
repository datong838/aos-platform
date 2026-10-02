# d2b3c4b 已接受方案内容生成执行前权威复核方案

上位：231-5 §5、§9；D-waves d2b3c4b。当前正式 G2 Skill Eval 来源缺失，原 AnalysisRuntimeReceipt producer 不能用 historical fixture 冒充。本波在现有失败封闭的生成 Host 上，接入已经存在的费用、模型、容量、事实和绑定读者，为原生产者就绪后的受限执行做准备；不解除 `execute`/`verify_receipt` 的新来源禁入。

## 文件级最小改动

1. `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_handoff_lineage.py`：RED 证明在原 Stage、Review Receipt、Task/Brief 已通过的条件下，当前分支没有调用模型/预算/事实/容量/绑定读者；新增顺序和错误中止用例。测试替身只证明调用顺序和无执行，不算正式来源或业务验收。
2. `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：在 `ContentGenerateHostService.revalidate` 的 `accepted-stage-v1` 分支，复用旧来源已有 `_agent_capability_authority`、`_route_budget_approval_authority`、`_fact_source_authority`、`_resolution_capacity_authority`、`_binding_authority`、`_binding_dependency_authority`。路由预算读者取得数据库当前时间后，再核 `cutoff <= checked_at < expiry`，避免前后检查间授权过期。使用原 Stage Owner 回读的获批 Plan 和命令当前精确 refs；任何一步失败即中止，全部通过仍显式 `Host is not wired`。旧四 Artifact 分支、预算写入、Provider 和当前真实库不变。
3. 跑专项和相邻回归、py_compile、diff 检查；浏览器核保持三阻断/禁用状态。验证证据落盘、精确提交、更新 01/06 与 D-waves。

风险：现有正式 G2 来源、OIDC、八配置、Host assignment/identity、Growth1.13 发布仍缺；本波不能把测试里替身读者返回的对象提升成当前权威。下一段需原 Analysis producer 与持久化 Review Receipt 的隔离同事务正反链，随后生成执行和人工评审同源消费者。
