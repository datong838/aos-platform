# W5c9m｜重复路由真实匹配候选与参数形状基线

方案 `m1@ce3737ac`。静态复核本地 FastAPI lazy `_IncludedRouter`：`_match` 按有效 candidates 顺序遇首个 `Match.FULL` 返回；生产 router 也是首次 FULL 即 `handle`。隔离短命进程仅调用各有效 route 的 `.matches(scope)`，**未调用任何 endpoint**、未启动 lifespan/端口/DB/商城源。

对 W5c9l 十组精确同 method/path 的代表请求，匹配候选均为先注册 endpoint、后注册 endpoint；首 FULL 分派基线仍是前者。具体十组顺序沿用 W5c9l audit。`GET /v1/datasets/example` 额外确认 `wave_ext.get_dataset` 在 `phase5_datasets.get_dataset` 前；源文件旧注释的第二条 Dataset GET 遮蔽由此得到无副作用匹配证据。

将模板变量名正规化为 `{}` 后另发现 **7 组参数路径形状碰撞**（各两个实际路由）：

- GET `/v1/aip/lineage/{}`：`{lineage_id}` / `{record_id}`；
- GET `/v1/datasets/{}`：`{rid}` / `{ds_id}`；
- GET `/v1/ontology/object-types/{}`：`{type_id}` / `{ot_id}`；
- GET `/v1/schedules/{}`：`{schedule_id}` / `{sc_id}`；
- GET `/v1/schedules/{}/runs`：`{schedule_id}` / `{sc_id}`；
- POST `/v1/schedules/{}/run`：`{schedule_id}` / `{sc_id}`；
- PUT `/v1/ontology/object-types/{}`：`{type_id}` / `{ot_id}`。

精确重复 10 + 参数形状重复 7 是两种不同计数，不代表仅有 17 个 endpoint；每组两个，且不能将 schema 字典覆盖与运行时实际错误等同。**风险焦点**：三个精确 POST 加 shape POST、shape PUT 若调序/删先者，会改变真实动作分派。文档去重应仅作用于 schema 展示层的后注册项，不删除/重排路由，不改鉴权/handler。下一波 W5c9n 先文件级方案锁住有效路由分派与 OpenAPI 正文路径选择的现状，再做最小修复和拒绝回归；不能假定只设 `include_in_schema=False` 就对已构建 OpenAPI 的 17 组全部安全，需要隔离实测。

8080 业务浏览器离线，真实 A0-V 12 Run no-authority 不变。
