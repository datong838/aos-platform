# SC4-5a 初始分析数据需求验证

2026-09-14；基线192d7add；m1单写者，不push。

新增AnalysisDataRequirementPreparation，在原事件当前事务中读取实际START Receipt/Case/Run/Compilation/初始Checkpoint，校验显式数据意图的当前Profile事实范围、原cutoff和来源有效期。通过同安装/代次/epoch/组的sealed data Host创建原DataRequirement和WAITING_DATA业务状态，TaskRun保持paused。无远程数据读取、无Fulfillment、无自动赋权、无经营步骤。

真实隔离库从上一波formal handle创建实际初始化链，首次需求成功，重复执行暴露replayed标记导致不可变journal冲突。修复DataRequirement Host：先原命令/状态转移核验，再复用原journal响应，业务正文差异仍拒绝；原SQL摘要/分派不可变校验不变。直接Host无journal路径保持原重放语义。

最终53 passed/7既有警告/15.42s，包含6个新PG场景：实际需求/重放、错事实/错cutoff/越期拒绝、外层故障回滚、同事件改变数据政策拒绝。其余formal初始化/原数据request/fulfill/适配器回归通过。AR2-7 1905/184/93五错误数组均空，diff check通过；memory GREEN 1101 Delivery/1084 Task/2701 events。

局限：来源/能力/安装计算仍为fixture，数据政策由测试显式提供；本段未接入自动安装政策计算，也未获得真实业务事实。主库/主服务未改变。因此不计真实首链或八场景完成。

下一SC4-5b：原PREPARING Receipt + actual DataRequirement/WAITING_DATA组合为续跑前置权威，保留旧WAITING_DATA Receipt兼容，禁止伪造回执；随后专用当前恢复门、自动政策/数据满足、真实分析。
