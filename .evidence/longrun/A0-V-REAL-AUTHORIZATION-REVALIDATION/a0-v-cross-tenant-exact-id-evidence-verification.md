# A0-V 跨租户 exact-id 证据修复验证

## 1. 结果

`A0V_CROSS_TENANT_EXACT_ID_EVIDENCE_GREEN`。

实现提交 `bdd837596bcdcc087e465dab45b1685eca81c1e1` 移除了“任意正向集合非空即证明隔离”的错误启发式。当前没有正向租户 AgentInstance，因此 `crossTenantResourceIsolation` 正确保留为 1 个 unverified。

## 2. 修改文件

- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/a0-v-readiness-collector.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/verify_a0_v.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/test_a0_v_readiness_collector.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/a0-v-readiness-result.json`

没有修改 API、数据库或租户数据。

## 3. 验证

| 检查 | 结果 |
|---|---|
| Python 编译 | GREEN |
| 全部 A0-V collector 专项单测 | 9 passed |
| 全局 6/37/10 目录非空、租户实例为空 | 隔离仍为 unverified |
| 正向 exact AgentInstance 200、canary 同 ID 404 | verified |
| canary 同 ID 返回 200 | `crossTenantResourceIsolation.canary=EXPECTED_404` blocker |
| JSON 阶段验证器 | `A0_V_EVIDENCE_VALID blockers=19 unverified=1` |

采集器新增 `/v1/aip/agents` 正向/canary GET；只有正向实例存在时才生成 URL-encoded exact-id 反查。当前 `observations.isolation={}` 与 unverified 一致，没有伪造验证请求。

## 4. 当前证据

`a0-v-readiness-result.json` 于 `2026-09-10T11:58:01.631569+00:00` 对提交 `bdd837596bcdcc087e465dab45b1685eca81c1e1` 采集，SHA-256=`050390a6dd65610e6eacf55193d6ccf25b86a3375b67e578bd8ba9ea5b69f95a`。

当前结论仍为 `A0_V_BLOCKED_WITH_ACTIONABLE_GAPS`：19 个 blocker、1 个 unverified。隔离 unverified 只能在后续合法租户安装产生实例后，以真实 exact ID 的 200/404 双向证据关闭。
