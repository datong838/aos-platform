# A0-V 安装运行态与 Workshop 就绪覆盖验证

## 1. 结果

`A0V_INSTALLATION_RUNTIME_WORKSHOP_READINESS_COVERAGE_GREEN`。

该标记表示 A0-V 已能精确区分历史安装记录、当前 active 安装、可用运行绑定和八模块可用性。隔离恢复环境仍为 `A0_V_BLOCKED_WITH_ACTIONABLE_GAPS`，不表示电商包已安装，不允许进入 A1。

## 2. 变更

- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/a0-v-readiness-collector.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/test_a0_v_readiness_collector.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/verify_a0_v.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/a0-v-readiness-result.json`

方案提交为 `2ec35b48`，运行语义校正提交为 `aa9d03d2`，主体实现提交为 `d342fbc7`，runtime exact-id 隔离测试补强提交为 `223ab8ae`。

## 3. 专项验证

| 检查 | 结果 |
|---|---|
| Python 专项 fixture | 15 passed |
| 空列表／只有历史安装 | `ACTIVE_INSTALLATION_MISSING` |
| 多个 active 安装 | `ACTIVE_INSTALLATION_AMBIGUOUS` |
| active/current/etag 指针漂移 | `ACTIVE_INSTALLATION_POINTER_MISMATCH` |
| 分页不完整或正文畸形 | `INCOMPLETE_OR_MALFORMED_COLLECTION` |
| exact runtime ready、已配置、已启用、无 fence | 通过 |
| runtime 运行中、停用、fence、未配置或修订漂移 | `RUNTIME_NOT_READY` |
| runtime exact ID 正向 200 / canary 404 | 通过 |
| runtime exact ID canary 200 | `bundleRuntimeInstallation.canary=EXPECTED_404` |
| 八模块精确且全部 available | 通过 |
| 模块缺失、重复或 degraded | 失败关闭 |
| Python 编译与 diff whitespace | 通过 |

## 4. 隔离恢复环境复采

结果文件于 `2026-09-10T12:25:44.687466+00:00` 对提交 `223ab8aeb941da73e2c646bfce22d5c78e90a731` 采集，SHA-256 为 `b5af007f9564445e3b80b6b552d3441069fcee7421e54eb4c46658edd8bc16a3`。

- A0-V 结果：`A0_V_BLOCKED_WITH_ACTIONABLE_GAPS`；
- blocker：18；
- unverified：0；
- `bundleInstallations`：HTTP 200、total=0；
- `workshopModules`：HTTP 200、count=0；
- runtime exact-id 请求：0 次，因为没有 active 安装 ID；
- 新精确根因：`bundleInstallations.active=ACTIVE_INSTALLATION_MISSING`、`workshopModules.readiness=EXPECTED_EXACT_EIGHT_MODULES`；
- 阶段验证器：`A0_V_EVIDENCE_VALID blockers=18 unverified=0`。

相较上一时点的 17 个 blocker，宽泛的 `bundleInstallations=REQUIRED_COLLECTION_EMPTY` 被 active 安装根因替换，并增加独立的八模块就绪门，因此总数为 18。该数量变化来自判定覆盖变严，不代表运行状态退化。

## 5. 一致性与风险

实现与 231-6 的“安装并配置电商包”首链前置、Installation 指针合同、runtime server-derived `ready` 状态及 Workshop 投影合同一致。全部新增采集为 loopback GET，没有修改数据库、安装状态、运行开关或外部系统。

当前恢复库源自 2026-08-05 历史备份，尚无 active 安装，因此 runtime 动态请求分支只能由 fixture 验证，不能冒充实机 ready 证据。下一阶段应先查明首装的 canonical 安装、审批与 runtime 生命周期路径，不能把 successor 更新脚本改造成无权威首装捷径。
