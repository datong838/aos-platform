# 首装登记请求与预览切片验收

2026-09-13 05:30，设计基线cc5b34e6；主任务既有API写入租约内串行施工。

RED：新模块不存在，测试收集ModuleNotFoundError。实现后27 passed（3.92s），7项既有警告及1项故意构造未校验模型带来的序列化警告。覆盖固定九项默认fenced、预览不是授权、预览修改不改变请求、任意控制字段拒绝、严格UUID/bigint/幂等键和exact目标变化hash不同、绕过构造的输入重新校验。

AR2清册1812模块/158分类/93迁移，五类错误列表为空。审查确认仅新增严格契约和纯预览，无数据库连接、授权更改、Handler执行、HTTP挂载或主库登记；CurrentInstallationRef、ConfigurationRef、canonical hash与幂等键校验复用既有契约，未复制权限状态机。

测试名称先通过rg确认不存在；未覆盖已有测试。未改已签名包，运行API无需为未接线纯契约重启。

下一波继续first-dispatch-registration-design-v2.md第2至5项：登记持久化Owner/权限评审、fenced首次登记的exact切换、正式API、未激活登记禁用卸载。当前依然不可宣称业务路由已登记或经营Case/Run已自然生成。
