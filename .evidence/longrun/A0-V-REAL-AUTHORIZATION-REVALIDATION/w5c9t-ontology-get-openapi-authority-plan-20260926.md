# W5c9t｜Ontology 三个精确 GET 文档权威切片

## 上位/禁止线

承接 231、W5c9l/m 十组精确与七组形状碰撞、W5c9n/q/r/s 只隐藏后置 GET 的兼容范式。已知 `GET /v1/ontology/branches`、`graph-health`、`object-types` 先在 `ontology` 路由、后在 phase4 路由；`POST /branches` 和 object-types 参数形状 PUT 也有碰撞，**本波不改任何写方法或顺序**。18181 旧代码、8080 离线、原 A0-V no-authority。

## 文件级和测试

- 静态复核 `services/aos-api/aos_api/routers/phase4_ontology_branches.py`、`phase4_ontology_types.py`、前置 `ontology.py` 与 domain manifest，确认三个目标 GET 都是后置且没有多方法 decorator。仅给三个后置 GET decorator 加 `include_in_schema=False`；若其中任一目标不符合，停止并缩小方案。
- 新增 `services/aos-api/tests/test_w5c9t_ontology_get_openapi_authority.py`：RED 固定三个后置 GET 仍公开；GREEN 固定原先可达前置 GET 成为文档权威、后置 route 仍注册但不展示，POST branches/PUT detail 和其它 phase4 合法文档仍存在；不调用 handler。
- `--noconftest`、后台开关 off；专项 + manifest 与四项既有文档累计。浏览器 8080 离线，真 DB/商城源/Worker/18181 都不碰。
- verification/精确提交/D-waves/AOS CAS/Prime；下波单独分析 POST/PUT 与参数形状，不用消警告之名激活旧写路由。

## 九步

1. 上位复习；2. 本方案先提交；3. RED；4. 三个 GET decorator 最小改动；5. 专项/累计；6. 方案/代码/写方法未变复审；7. 浏览器离线；8. 证据/记忆/提交；9. 自动下一波。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
