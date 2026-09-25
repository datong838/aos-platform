# W5c9k 补订｜schema 字典遮蔽原始路由重复

首轮按原方案一次离线运行返回 `operation_id_collision_count=0`、`path_method_duplicate_count=0`，但同波 W5c9j 真正生成时已有重复 Operation ID 警告，`phase5_datasets.py` 顶部还明确注明两个 GET 被前序路由抢占。此处 0 仅说明**审计方法不足**：OpenAPI `paths[method]` 是唯一键，会覆盖同 method/path 的重复定义；顶层 `app.routes` 14 不是所有被展平的原始子路由表，直接按它计数亦可能漏掉。

允许第二个、最后一个 90 秒有界离线诊断进程：先打印顶层路由的安全类型/路径/子路由数量，再递归子路由（若存在）统计 method/path 与 `unique_id` 冲突，只输出冲突方法/路径/端点模块名，不打印 schema 或请求字段。若仍无法解码原始路由层级，停止本波于 UNKNOWN，不再追加运行；不得从 schema 0 推出无冲突。零执行/无 lifespan/无端口/无商城源边界不变。
