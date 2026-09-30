# W5CB4 BG00EF｜运行策略候选与 kill switch 一致性

## 方案复习与缺口

复习 231 主计划 A1、231-1 四层边界、231-3 安装/配置状态机，BG00a/az/cx/ED 的正式候选与 RuntimePolicy Owner。`RuntimeInstallationPanel` 把八类候选数展示为“当前配置权威候选”，明确不等于安装绑定/运行准入。`configuration_source_catalog.read_source_catalog` 对运行策略只列 current active 且 `killSwitchEnabled=false`；`runtime_configuration_candidates.read_candidates` 目前只计 current active。这样 kill 已开启的策略会被计成候选，但配置选择目录不会提供它，页面误导操作者。

## 文件级最小改动与 RED

| 文件 | 改动 |
| --- | --- |
| `services/aos-api/tests/extension_runtime/test_runtime_configuration_candidates.py` | 使用 pytest 自动生成且会销毁的测试库，同一租户内新增唯一 active+kill 策略后计数不变，active 非 kill 后计数+1。先运行预期 RED。目录已有 `policy_kill` 专项覆盖不提供该策略。 |
| `services/aos-api/aos_api/extension_runtime/runtime_configuration_candidates.py` | 仅运行策略计数增加与目录一致的 `payload->'killSwitchEnabled'='false'::jsonb` 过滤；八类其余 SQL、租户/安装门、API 不动。 |

验收：专项候选/目录测试、邻接后端累计通过；失败/未知不得显示可用候选。当前真库只读，仅 pytest 自动生成测试库内事务写并回滚。无网络 active、Host/worker/Provider 或外部动作；浏览器只在 browser-pilot 可用时验证，不能用单元测试冒充截图。方案/代码复审核对计数仍不等于准入。
