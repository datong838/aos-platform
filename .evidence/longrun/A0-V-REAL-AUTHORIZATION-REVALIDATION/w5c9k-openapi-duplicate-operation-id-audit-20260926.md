# W5c9k｜重复 Operation ID 审计器盲点与停止

方案 `m1@11a920e0`；补订 `m1@f613b95f`。首个离线进程从生成后的 OpenAPI `paths[method]` 聚合与 `app.routes` 顶层对象聚合，得到 operationId/path+method 重复均 0。这个 0 **不是系统无冲突**：OpenAPI 字典不能容纳相同 method/path 两个条目，可能已覆盖；生成时历史已有重复 Operation ID warning。

静态源码明确 `phase5_datasets.py` 注释：`GET /v1/datasets` 与 `GET /v1/datasets/{id}` 被前序 wave_ext Data OS 路由抢先匹配，标记 `NOT_REACHABLE_DUPLICATE`。`domain_aggregates.py` 在 Data 域包含 phase5 schedules/datasets，但 FastAPI 现版本 `APIRouter.include_router` 只向顶层放 `_IncludedRouter`。第二个、最后一个离线进程读到 4 个 docs route + 10 个 `_IncludedRouter`，从 `.routes` 递归得到的 leaf 仅 4，重复仍为 0，证实分类器漏掉延迟展开层。

已静态定位依赖库 `fastapi.routing.iter_route_contexts(routes)` 通过 `_IncludedRouter.effective_route_contexts()` 展开，与 OpenAPI 构建实际采用的入口一致。因补订明确“第二次最后一次，仍无法解码则停止”，本波未执行第三次；精确冲突数/全部方法路径仍 **UNKNOWN**。不要借两个 0 改 API 命名、路由顺序或宣称冲突消失。W5c9l 另立方案，用依赖库迭代入口在隔离进程精确列示路由/operationId，并专测已知 Dataset 被遮蔽处；任何兼容修复再下一波最小变更。

无真实 API/DB/Worker/商城源操作，18181/原组 no-authority 不变。
