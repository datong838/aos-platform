# AgentRun 原始 Query 执行期留存方案

日期：2026-09-11

基线：`cc65dbe6`

状态：实施前冻结

## 目标

让明确开启正文留存的受治理 `AipAgentRunExecutor` 在 Provider 调用前，将原始 query 写入
`agent_query_input` 私有 Owner。写入必须绑定同租户的 TaskRun、AgentRun Attempt、
`requestHash`、`contentHash` 与 marking，且通用 Artifact payload 不包含正文。

## 军规与边界

- 复用既有 `retain_output_text=True` 作为本次分析生成的显式正文留存选择；默认值仍为
  `False`，普通 AgentRun 不新增输入正文留存。
- 输入 Artifact 必须在 Attempt 已创建且仍为 `PREPARED`、Provider 尚未调用时写入。
- 输入写入失败时，Attempt 只允许从 `PREPARED` 转为 `FAILED`，reason 为
  `INPUT_ARTIFACT_WRITE_FAILED`，AgentRun 同步为 `FAILED`，不得调用 Provider。
- Artifact ID 由租户、Attempt ID 与 Artifact 类型确定性生成；同一 PREPARED replay 只能
  验证并复用同一正文，不能生成第二份输入。
- 输出 Artifact 的 source 同步记录 Attempt 的 `requestHash`，为后续 query/output/Eval
  同源核验提供精确锚点。
- 本波不创建 Eval、不启动真实经营任务、不增加路由或 operation，不改变预算、审批、
  Provider unknown 与重放规则。

## 文件与 preHash

| 文件 | preHash | 修改 |
|---|---|---|
| `services/aos-api/aos_api/aip_agent_run_executor.py` | `2e73893a4b7a8ba07060170e5a61f16d169a09c68b891dd796e2f74f7b27fa80` | Provider 前写 query Artifact、失败收口、输出 source 绑定 requestHash |
| `services/aos-api/tests/aip/test_aip_agent_run_executor.py` | `ffe6e220eb3693d5d91136becf93fbda56fc090ad062cf9031d2a5f4ef2b7fad` | 正向顺序、默认不留存、失败不调用 Provider |
| `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md` | `abe00a5ab33816cf499154eca172e750a8da188c0b1d4b9b7dc949cacba1c37c` | 登记 9.6 增量切片 |

## 退出条件

1. 显式正文留存模式先写输入 Artifact，再 reconcile/调用 Provider，随后写输出 Artifact。
2. 输入 payload 无 query 正文；私有写入参数含原文，哈希与 Attempt `requestHash` 精确。
3. 输入写入失败时 Provider 调用数为 0，Attempt/AgentRun 均为 FAILED。
4. 默认模式不写 `agent_query_input`，既有输出、UNKNOWN、重放语义测试保持通过。
5. 相关单测、Python 编译与 closure 验证通过，生成验证文档并仅提交清单文件。

## 后续边界

完成本波后，下一波才允许让阶段评审读取 query Artifact，并以包内规则从原始 query 与
原始 output 派生正式 Eval case；本方案本身不证明真实经营闭环完成。
