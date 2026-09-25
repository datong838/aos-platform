# W5c9q｜Builds 重复 GET 文档单一权威最小切片

## 上位/现场

231 每波方案→专项→累计→浏览器→证据；W5c9l/m 证 `GET /v1/builds` 先 `wave_ext.list_builds`、后 `builds.list_builds` 同 method/path；W5c9n 的 Dataset 两个 GET 文档去重已有 no-dispatch-change 范式，W5c9p 路由测试可无 DB 安全回归。原组 no-authority、8080 离线、18181 旧代码未重载。

## 文件级清单

- 只改 `services/aos-api/aos_api/routers/builds.py` 中后置 `GET /v1/builds` 的 decorator `include_in_schema=False`，保留 endpoint/路径/注册顺序/鉴权/其它 Build API。先只读核对该模块路由和 wave_ext 注册位置；若不是唯一后置 GET 或存在 GET/POST 混合行为，停止并补方案。
- 新增 `services/aos-api/tests/test_w5c9q_builds_openapi_authority.py`：RED 先证后置仍在 schema；GREEN 锁住两 route 仍注册、前置可达 endpoint/文档权威、后置不进 schema、其它 Build 文档保留；绝不调用 handler。
- `pytest --noconftest`、Host=0/Cron=false/snapshot=false/migration disabled；专项、路由 manifest/Dataset 文档累计，不能进入真实 DB/源/Worker。浏览器 8080 离线。真实 18181 不重启。
- 方案/代码一致性复审及安全提交、D-waves/AOS CAS/Prime；下一波继续下一组 GET 文档冲突，写端点另立严门。

## 九步

1. 复习 231、W5c9l/m/n/p；2. 本方案先提交；3. RED；4. 一行 decorator 最小改动；5. 专项/累计 `--noconftest`；6. 文档/运行时分派复审；7. 8080 浏览器离线如实记录；8. verification/精确提交/记忆同步；9. 自动下一波。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
