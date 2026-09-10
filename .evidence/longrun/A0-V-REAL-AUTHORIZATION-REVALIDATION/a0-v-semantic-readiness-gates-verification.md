# A0-V 语义就绪门修复验证

## 1. 结果

`A0V_SEMANTIC_READINESS_GATES_GREEN`。

修复提交 `14a1dcc81aa86dd2f9201d8ee7f7532fe4e112cc` 使 A0-V 判定从“接口可读/集合非空”提升为业务语义检查。该标记只证明采集器会可靠地失败关闭，不表示 A0-V 或真实业务链已 GREEN。

本阶段采集时 A0-V 总结论为 `A0_V_BLOCKED_WITH_ACTIONABLE_GAPS`，共 19 个 blocker、1 个 unverified。随后 `ef18123f` 修正首链前置分类，当前总数变为 16 个 blocker、1 个 unverified；本文件的 19 项保留为语义门首次启用时的时点证据。

## 2. 修改文件

- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/a0-v-readiness-collector.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/verify_a0_v.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/test_a0_v_readiness_collector.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/a0-v-readiness-result.json`

没有修改业务 API、数据库 schema、运行配置或租户记录。

## 3. 确定性验证

| 检查 | 结果 |
|---|---|
| Python 编译 | GREEN |
| ready fixture | 0 semantic blocker |
| blocked SourceReadiness | `STATUS_BLOCKED` + `SOURCE_NOT_READY` |
| 过期模型健康 | `NO_FRESH_HEALTHY_PROVIDER` |
| Agent 数量不足 | `COUNT_MISMATCH` |
| Capability available 不足 | `COUNT_MISMATCH` |
| 畸形正文 | `MALFORMED_READINESS_BODY`，采集器不崩溃 |
| 专项单测 | 3 passed |
| JSON 阶段验证器 | `A0_V_EVIDENCE_VALID blockers=19 unverified=1` |

模型的 route resolution、健康、六节点 chain 和 CNY hard-stop budget 由语义门单独检查；基础非空检查只保留 provider、model 和 route 三个事实，避免一个 gate 重复计数。

## 4. 本阶段采集事实

`a0-v-readiness-result.json` 于 `2026-09-10T11:33:36.510891+00:00` 对提交 `14a1dcc81aa86dd2f9201d8ee7f7532fe4e112cc` 采集，SHA-256=`2ed61a4b9b9d7c570dff92b85f8719ca004035b813452af7eeae17d04e6b882b`。

19 个 blocker 分为：

- SourceReadiness 2 项：总状态 blocked，12 个来源中存在未就绪项；
- Workshop/AIP/Capability 4 项：Workshop 未安装，AIP 电商 catalog 尚无合法 6/37/10 定义与 6 个 runnable 安装实例；
- Bundle 与生产合同 6 项：安装、ProductionContext、StartDecision、ResponsibilityPlan、StageTemplate、TaskBrief 为空；
- Model 7 项：provider、model、route 为空，且无 ready resolution、有效健康、ready 六节点 chain 和激活的 CNY hard-stop budget。

unverified 仍是 `crossTenantResourceIsolation`：当前没有正向 exact-id 资源可供负向租户反查。缺 Bearer 返回 401、非法 limit 返回 400，运行期间 migration、QYH Cron、Logic automation 与 Provider health maintenance 均保持 disabled/inactive。

## 5. 一致性与风险

本次实现与修复方案中的 Source 12 项、Agent 6/37/10、Capability 10、Model 健康/链/预算要求一致。恢复数据库仍来自 2026-08-05 历史备份，因此 19 项是“可恢复环境的当前可验证缺口”，不能冒充 2026-09-10 原运行库的真实配置快照。

生产合同目前仍只校验集合非空。写入或重建这类配置前必须先读取 exact-current API 契约并补齐语义门；在此之前不得以任意占位记录关闭 blocker。
