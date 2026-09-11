# 经营参谋分析来源宿主端口验证

2026-09-11，基线 `m1@8f0640fb`。

实现结果：growth SDK 新增租户绑定的只读 `GrowthAnalysisSourcePort`；包内
`read_authorized_analysis_bundle` 严格校验有界参数，只调用宿主一次，再复用 exact
来源材料完整性校验。宿主 `BoundEcommerceGrowthAnalysisSourcePort` 只接受
`HostTransaction` 和构造时绑定的 `TenantScope`，不能接收调用方租户覆盖，也不会把
原始连接交给包。

第一次聚焦执行出现 `25 failed / 32 passed / 1 skipped`。所有失败都发生在包模块导入阶段：
类型注解直接导入 `sdk_ports`，使原本可独立加载的来源合同间接依赖未加入测试路径的
`aos_extension_sdk`。修复为 `TYPE_CHECKING` 下的类型导入，没有放宽运行合同。随后同组
复跑为 `57 passed / 1 skipped`。

联合回归覆盖包来源、宿主绑定端口、既有宿主 Owner 来源读取、proposal、structure case
和 structure eval，共 `141 passed / 1 skipped`，4.10 秒。skip 是既有、需显式
`AOS_GROWTH_DRAFT_FULL_GRAPH_TEST=1` 的可抛弃数据库全图测试，本切片没有改变其授权门。

三个变更模块 `py_compile` 通过。第一次 `verify_closure.py --phase ar2-7` 扫描 1,763 个
Python 模块，仅发现新增宿主端口尚未在清册分类；补入清册 9.3 后再次执行通过，hash、
正向依赖、反向调用、跨层导入和动态引用错误均为空。

本切片保持只读、无 Provider、无 Receipt、无 operation 注册、无真实租户激活。成功
AgentRun 的原始 query/Artifact 与正式 Eval target 仍未接入该端口，是下一切片。
