# W5c9n｜Dataset 两条不可达 GET 的 OpenAPI 单一权威

## 上位/产品/技术复习

231 业务工作台要求真实可用入口、专项/累计/浏览器与方案一致性；W5c9l/m `m1@f1730363`/`158c7130` 已证 `GET /v1/datasets` 精确重复和 `GET /v1/datasets/{rid}` vs `{ds_id}` 参数形状重复：`wave_ext` 先注册、`phase5_datasets` 后注册，代表请求先命中 `wave_ext`。`phase5_datasets.py` 顶部既有 `NOT_REACHABLE_DUPLICATE` 注释。不可把后者变为运行时可达或改变鉴权/数据。

## 文件级最小清单

- 仅修改 `services/aos-api/aos_api/routers/phase5_datasets.py` 的两个 GET decorator：标 `include_in_schema=False`，保留 endpoint、路径、注册顺序、依赖、全部其它 POST/preview/builds/health 路由。
- 新增 `services/aos-api/tests/test_w5c9n_dataset_openapi_authority.py`：RED 阶段证明两后置 GET 当前仍进 OpenAPI；GREEN 锁定有效路由首匹配者不变、后置两 route 仍注册但不进 schema、schema 精确两个 GET 只发布 `wave_ext` 可达权威；验证其它 Dataset 操作仍在 schema。禁止调用真实 GET/POST handler。
- 只在无 lifespan、无端口的测试进程运行；显式 Host=0/Cron=false/snapshot=false/migration disabled；不读商城源、不触碰真库。需要完整 app import，但不可启动 Uvicorn。先专项，后受影响路由/manifest 累计回归；浏览器 8080 离线诚实记录。
- 若 `include_in_schema=False` 使其它 Schema/现有契约异常，回到方案复审，不扩大改动。W5c9o 再处理其它 exact/shape 碰撞。

## 九步

1. 复习 231、W5c9m、现有路由 precedence 测试。
2. 本方案先提交，保留 m1/18181/租约前检。
3. RED 测试锁住旧失败和兼容性。
4. 两 decorator 最小实现。
5. 专项 + 受影响累计测试。
6. 确认无运行时行为/鉴权/写操作变化，文档确指可达 GET。
7. 8080 业务浏览器离线，离线 OpenAPI 不冒充业务验收。
8. verification、m1、D-waves/AOS CAS/Prime。
9. 自动 W5c9o 处理下一组文档冲突，先方案。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
