# W5c9m｜重复路由分派兼容基线与文档单一权威设计

## 上位边界

W5c9l `m1@f1730363`/AOS-000700 已证 4,515 有效 method routes、十组 method/path 与 Operation ID 重复。静态注册顺序不能直接当实际分派事实，尤其三个 POST 不能因清理文档意外改换处理者。原组 no-authority/商城源禁读/8080 离线不变。

## 文件级与测试计划

- 只读复习 `main.py`、`domain_aggregates.py`、FastAPI 当前 `routing.py` 的 lazy `_IncludedRouter` 匹配规则，`phase5_*` 与 `wave_ext`/ontology 冲突端点。检查已有路由测试/manifest 标注，不修改 API。
- 一次 90 秒短命、无 lifespan/端口/DB/源进程；通过框架路由**匹配函数**而不是调用 endpoint，对十个精确 method/path 与 Dataset detail/其它参数形状代表路径取命中的 endpoint 模块名；不触发 GET/POST 处理器。若 matcher 属性/Scope 不明确即停止 UNKNOWN，不向运行中的 18181 发 POST。
- 对每组分类为“先者实际匹配、后者不可达”“参数形状另有遮蔽”“无法判定”。文档修复只允许隐藏/标记后者 schema，而不能删除路由、调序、更改权限/handler 或让不可达 POST 变可达；任何破坏旧 API 文档引用的影响先在下波方案处理。
- 本波无代码，audit/verification、D-waves/AOS CAS/Prime。若结果稳定，W5c9n 再按文件级清单最小文档去重 + 单元负例测试；若不稳定，继续诊断。

## 九步

1. 复习 231/W5c9l 和零执行边界。
2. 本方案先提交。
3. 静态确认 matcher API 与已有验收。
4. 一次有界、纯匹配离线基线。
5. 无代码时专项为 matcher 结果，累计不冒充。
6. 方案/代码/兼容/写端点风险复审。
7. 8080 业务浏览器离线。
8. audit/verification、精确提交、D-waves/AOS CAS/Prime。
9. 自动 W5c9n 最小文档去重计划/实现或继续诊断。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
