# W5CB4 当前源码新隔离库结构子波核验（2026-09-27）

## 已达到的边界

- 新建专属 `aos_current_preview_20260927`，数据库 owner `aos_app`，PUBLIC CONNECT 已撤；从空库经正式 Alembic/平台初始化到唯一 `a0v_106`，只读回读 566 张 public 表。原 `aos_meta_head` 仍 `a0v_092`，8080 隔离克隆 HTTP 仍 200，未切换页面。
- 新库 `twa_org` 仅有 `org-org` 1 行、`dev-org` 0 行；`asset_bundle_version=0`、`bundle_installation=0`。所以本子波**不是** Registry/安装/Runtime/浏览器验收通过。

## 过程与故障对账

- 实施前只读确认新库名不存在，显式 `CREATE DATABASE ... TEMPLATE template0` 后精确回读；迁移 intent 留在 `/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/migration-state`，不删除。
- 首次迁移因应用 DSN 格式错误在 `228assetintegration` 后停止；读回版本和表数再修正。再次发现旧 `twa_*` 初始化与 `object_lifecycle` 前置缺口；均在同一可核边界修复，并让续跑只接受 intent 与 `228assetintegration` 一致。未删库、未从头重放未知命令。最终 `migration-result.json` 为 `CURRENT_PREVIEW_SCHEMA_READY`，before 63 表/`228assetintegration`，after 566 表/`a0v_106`。
- 新入口默认只读、显式 `--migrate` 与 `--resume-after-assetintegration`，状态已存在、非精确版本均失败关闭；数据库异常输出只含错误类型/SQLSTATE/主消息，不输出 DSN。专项 `2 passed, 7 warnings`，脚本编译和 `git diff --check` 通过。

## 下一波

按同一新库的正式 RegistryService 发布四个 exact 当前签名包，creator/validator/publisher 分离；独立读回版本、签名/内容/证据与零安装。之后才 Composition/Installation maker/checker。任何部分发布或未知结果先只读对账，不重发；原库、旧 12 Run、商城源和自然 worker 均不触碰。
