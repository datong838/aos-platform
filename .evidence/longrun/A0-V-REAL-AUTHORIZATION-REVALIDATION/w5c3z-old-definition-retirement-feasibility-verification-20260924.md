# W5c3z 旧 DR 定义退休可行性只读验证（2026-09-24）

方案 `5ba29de5` 的只读盘点完成。旧 DR definition `446cc1ae-fa5b-406a-9446-d32104126dda` head rev3/hash `sha256:48e236e8e5951defd0cb91cd9d52afc8bec287241804bd3202713ae03cfc22bd`、state disabled，12 current member 仍占位，12 schedule off。旧 DR installation `89975129-7e0f-4860-ac56-7a031ebe4a1a` **仍 active/etag5**，三资源 3/3 released；actor `a0v-ecommerce-growth-1.4-runtime-owner` 的租户角色 admin。

12 槽位历史 Run 共 53，running=0、executor 未证明停止=0、按正式 Owner retire 条件阻断数=0。旧定义关联 saved group 1 个，unfinished group=0；仅查状态/引用，未读运行 payload 或商城源数据。第三继任者 Resume 审计仍绿，零在途/零 canary。

判断：`_released_retirement_allowed` 的“已卸载旧安装”特例**不适用**（DR 仍 active），但这并不等于必须卸载 DR；现行 `CurrentConfigurationPermission` 仍可在锁定旧 DR 安装后核 actor 的正式角色、标记和 lock。因此下一波先精确检查该权限和独占状态，再由原 `PipelineSnapshotScheduleDefinitionOwner.transition(intent='retire')` 单次退休；若权限/标记或历史组状态不满足，保持 disabled、不直改数据库。退休前不允许配置新定义。
