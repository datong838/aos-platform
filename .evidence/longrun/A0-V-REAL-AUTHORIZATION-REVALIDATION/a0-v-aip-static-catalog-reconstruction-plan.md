# A0-V AIP 静态目录隔离重建方案

## 1. 目标

在只连接 18435 隔离恢复克隆 `aos_meta_head` 的前提下，使用已有 canonical `AipSolutionPackPublisher` 从仓库当前 ecommerce-growth bundle 重建全局 AIP 静态定义，使 API 能精确回读 6 个 AgentTemplate、37 个 SkillTemplate、10 个 CapabilityDefinition。

这是恢复环境的显式重建，不是从 2026-09-10 丢失运行库中恢复出的当前配置，也不直接使任何租户 Agent runnable。

## 2. 权威与边界

- 输入只取当前仓库 `bundles/solutions/ecommerce-growth`；
- 执行入口只用 `services/aos-api/scripts/publish_ecommerce_growth_aip.py`；
- publisher 已有测试证明 bundle 身份/版本/交叉引用漂移先于发布失败，重复发布幂等，且不会创建 `aip_agent_instance`、Skill/Capability Binding、AgentRun 或 Handoff；
- 仅修改隔离恢复克隆中的全局定义表；不修改原样历史库 `aos_meta`、共享/生产数据库、租户安装或运行绑定；
- Provider 调用、费用、Secret 读取、外部发送/发布和 230 L0 均为 0/禁止。

## 3. 执行顺序

1. 登记独立 `A0-V-AIP-STATIC-CATALOG-RECONSTRUCTION` Task/Lease；
2. 通过当前 18181 进程已持有的数据库连接环境启动 publisher，不输出 DSN 或 Secret；
3. 连续执行两次，要求两次结果完全相同且均为 6/37/10；
4. 只读回采正向与 canary Agent registry、Capability catalog 和 runtime readiness；
5. 正向应能读取全局定义但 installed/runnable/available 仍为 0；canary 同样不得获得正向租户实例；
6. 重跑 A0-V 采集器和验证器，记录 blocker 的精确变化；
7. 形成证据、完成 Task、释放 Lease。

## 4. 停止规则

- publisher 目标不是 `aos_meta_head@127.0.0.1:18435` 时不执行；
- bundle 校验、第一次发布、第二次幂等回放或 API 回读任一不符合精确计数时停止，不继续租户安装；
- 发现任何租户运行行随静态发布新增时判失败并停止；
- 不为了得到 runnable/available 而在本任务创建 Binding、激活 Agent 或伪造健康。

## 5. 完成标记

`A0V_AIP_STATIC_CATALOG_RECONSTRUCTION_GREEN` 仅表示隔离恢复库中静态 6/37/10 目录已由 canonical bundle 幂等重建。租户安装、Binding、Agent 激活、StageTemplate/ResponsibilityPlan 物化仍是后续独立任务。
