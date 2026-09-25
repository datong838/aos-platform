# W5c9u｜剩余写方法与参数形状碰撞的文档权威审计

## 上位/冻结

W5c9l/m 确认十组精确 method/path + 七组参数形状重复；W5c9n/q/r/s/t 已只隐藏七组精确 GET 的后置文档项。剩余三组精确 POST（Ontology branches、Pipelines、Schedules）及七组参数形状含 POST run、PUT object-types，不得因“消警告”重排/删除路由、放宽鉴权或实际调用写 handler。原 A0-V no-authority、18181 旧进程、8080 离线不变。

## 文件级与只读范围

- 静态核对应前置/后置的 `ontology.py`、`phase4_ontology_branches.py`、`phase4_ontology_types.py`、`wave_ext.py`、`phase5_pipelines.py`、`phase5_schedules.py`、AIP lineage 相关路由及 `domain_aggregates.py`；明确七组参数形状的两个模板与其 first-match 可达者，不输出请求数据。
- 一次 90 秒无 lifespan/DB/端口隔离进程：用 `iter_route_contexts` 列 3 exact POST + 7 shape 的端点顺序、`include_in_schema`、OpenAPI 路径是否同时存在以及 schema 中同 method 操作的 tags/ID。只输出路径、方法、模块/计数，不请求任何 GET/POST/PUT endpoint。
- 如果所有后置项确实不可达且已有独立真实功能入口，下一波分为写方法文档隐藏与 shape 文档隐藏两个小切片；每个要先负例锁住先匹配者/鉴权/后置仍注册/其它合法文档。若某项与实际分派不一致，停止设计并另立诊断，不能推断。
- 本波只 audit/verification，不改生产路由；专项为静态+隔离读回，累计历史测试不冒充新实测；8080 业务浏览器离线。D-waves/AOS CAS/Prime 收口后自动下一波。

## 九步

1. 复习 231/W5c9l/m/t；2. 本方案先提交；3. 静态源审；4. 一次有界路由/schema 审；5. 无代码专项；6. 方案/代码/写端点风险复审；7. 浏览器离线；8. audit/verification/提交/记忆；9. 自动 W5c9v 最小修复方案。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
