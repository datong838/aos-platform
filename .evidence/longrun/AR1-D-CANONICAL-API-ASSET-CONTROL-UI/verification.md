# AR1-D Canonical API／资产控制 UI 验收记录

日期：2026-09-07

租户：`org-org/dev-project`（只读验收）

结果：`AR1_D_CANONICAL_API_ASSET_CONTROL_UI_GREEN`

## 交付事实

- Canonical runtime view 与 operation readback 已接入实际 FastAPI 路由；写入口继续要求服务端权限、`If-Match` 与幂等键。
- 生产只读视图使用 `PostgresInstallationStore(connect_read_only)`；UI 会话由 `ProductionUiSessionResolver` 从当前 Installation exact composition lock、Registry release、release policy、allowlisted bundle source、frontend manifest 与 entrypoint digest 联合解析，任一事实缺失即 `ui=null`。
- 资产控制页展示安装与运行两套状态；确认框会在离线、读取过期、刷新中、动作撤回或 binding 身份变化时关闭，预发送阻断不会丢失原幂等恢复句柄。
- `ExtensionHost` 只挂载服务端签发的资源会话，使用 sandbox iframe、一次性 nonce 与 MessageChannel；重复 `contentHash`、越界 route、缺失 handler、错代次／epoch 和声明外 operation 均 fail closed。

## 验证

- 后端相关累计：`1215 passed, 450 skipped`；跳过项均为既有条件门，不用于把缺失环境声明为通过。
- 前端累计：`280` 个测试文件、`2499 passed`；生产构建通过。
- OpenAPI 确定性导出、Python/TypeScript 编译及 `git diff --check` 通过。
- 跨源隔离链：`isolated-host-browser.json` 为 PASS，实际链路为 Canonical HTTP API → React host → sandbox iframe → MessageChannel → claimed read/command；声明外 read 被拒绝。
- 三视口：`browser-acceptance.json` 在 1280×720、1440×900、1920×1080 全部 PASS；运行存储缺失时展示固定中文原因且运行按钮数为 0。
- 内置浏览器实点：完整左侧菜单存在且可滚动；切换真实栖月汇安装记录后，revision、审批结论、事件时间线与 evidence 同步刷新。三视口落盘截图见 `asset-control-1280x720.png`、`asset-control-1440x900.png` 与 `asset-control-1920x1080.png`。
- 独立 Prime 最终终审：PASS；终审另行执行最新前端专项 `17/17` 通过，未发现剩余确定性代码阻断。

## 宽口径基线说明

一次全后端基线运行结果为 `12646 passed, 1041 skipped, 130 failed, 5 errors`。红项属于既有环境／不可逆迁移及其他域基线，未在本波中被隐藏或扩权修复；本波实际影响域的 asset-registry＋extension-runtime 累计门已全绿。后续 AR2 开工时继续先跑其精确受影响集，不把全仓既有红项表述为本波回归。

## 边界与下一波

- 本波未执行真实租户装卸、真实业务数据写入、共享迁移、OCI 创建、Provider 调用、计费或发布。
- 本波只证明 Canonical API、运行控制 UI 与隔离前端宿主可用；真实业务场景计数仍为 `0`。
- 下一波自动进入 AR2：按 N1～N8 精确闭包迁移经营分析→建议→内容任务的实际电商代码制品，并在隔离环境完成装卸／重装与旧入口失效反证；A0-V 之后才进入 A1 栖月汇真实自动首链。
