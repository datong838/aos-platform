# A0-V 首链前置条件分类修复验证

## 1. 结果

`A0V_FIRST_CHAIN_PRECONDITION_CLASSIFICATION_GREEN`。

实现提交 `ef18123f2929b7a519e91bb1aefa2ff584ccc563` 将 A0-V 静态前置与 A1 动态输出分开判定。当前 A0-V 仍为 `A0_V_BLOCKED_WITH_ACTIONABLE_GAPS`，共 16 个 blocker、1 个 unverified。

该标记只证明前置分类与失败关闭逻辑正确，不表示 StageTemplate、ResponsibilityPlan 或任何首链配置已经存在。

## 2. 修改文件

- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/a0-v-readiness-collector.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/verify_a0_v.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/test_a0_v_readiness_collector.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/a0-v-readiness-result.json`

没有修改业务 API、数据库、租户记录、运行配置或外部系统。

## 3. 确定性验证

| 检查 | 结果 |
|---|---|
| Python 编译 | GREEN |
| 专项单测 | 7 passed |
| 三类 A1 动态集合为空 | 不产生 A0-V non-empty blocker |
| StageTemplate 错 profile/draft/blocked/多候选 | 分别以 missing/not-frozen/not-ready/ambiguous 失败关闭 |
| StageTemplate 阶段漂移 | `INVESTIGATION_TEMPLATE_NOT_READY` |
| ResponsibilityPlan 槽位不足 | `INVESTIGATION_PLAN_NOT_READY` |
| 列表 count 与 items 不一致 | `COLLECTION_COUNT_MISMATCH` |
| JSON 阶段验证器 | `A0_V_EVIDENCE_VALID blockers=16 unverified=1` |

## 4. 当前采集结果

`a0-v-readiness-result.json` 于 `2026-09-10T11:45:02.564343+00:00` 对提交 `ef18123f2929b7a519e91bb1aefa2ff584ccc563` 采集，SHA-256=`1ccc4b5e37956293775f58f474e0b2c32ed2c31cc7f9320bc24b3ae717ce7d70`。

三项循环依赖 blocker 已移除：

- `productionContexts`：具体 run 准备完成后形成；
- `productionStartDecisions`：生产启动动作形成；
- `taskBriefs`：exact 评审 ACCEPT 后形成内部 TaskBrief。

它们仍持续 GET、校验集合结构、租户声明和 canary；缺失没有被伪装为 READY。

两个真正静态前置仍明确阻断：

- `stageTemplates.authority=INVESTIGATION_TEMPLATE_MISSING`；
- `responsibilityPlans.authority=INVESTIGATION_PLAN_MISSING`。

其余 14 项覆盖 Workshop/Bundle 安装、AIP 6/37/10 catalog、SourceReadiness 12 来源、Model Provider/Model/Route/Resolution/Health/Chain/Budget。unverified 仍为没有正向 exact-id 资源可用于负向租户反查。

## 5. 一致性与风险

实现与 A0-V“不执行 A1”边界、调查 authority materializer 和运行期 composition resolver 一致。恢复数据库仍是 2026-08-05 历史备份，16 项只能解释为当前隔离恢复环境可验证缺口。

下一步应处理静态 AIP 定义、安装与调查 authority 的合法物化顺序；不得通过占位 TaskBrief、伪造 ProductionContext 或预造 StartDecision 来关闭 A0-V。
