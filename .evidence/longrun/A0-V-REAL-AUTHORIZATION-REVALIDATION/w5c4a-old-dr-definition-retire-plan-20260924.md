# W5c4a 旧 DR 定义正式退休方案（2026-09-24）

W5c3z `b33f2919`：旧 definition `446cc1ae-fa5b-406a-9446-d32104126dda` rev3 disabled/hash `sha256:48e236e8e5951defd0cb91cd9d52afc8bec287241804bd3202713ae03cfc22bd`；12 current member，12 schedule off；53 历史 Run 均终结/已停，saved group 1/unfinished0；旧 DR installation active/etag5、资源 3/3 released，actor 租户 admin。第三继任者 operation resumed、九路/Host 正常。

1. 写前重读 W5c3z/W5c3x、精确旧 head/ref、12 member/调度、Run 阻断0、无在途、canary0；新唯一 retire key 和私有 0600 intent 在正式调用前固定。
2. 原 `PipelineSnapshotScheduleDefinitionOwner(controls=None, installation_store=PostgresInstallationStore())` 使用租户 scoped runtime connection，先经 `CurrentConfigurationPermission` 核当前 DR lock、actor 角色与标记。仅一次 `transition(intent='retire', expected_ref=rev3)`；若拒绝，留 intent 并只读对账，不重发、不直改表。
3. 正式成功须旧 head rev4 retired/唯一 retire revision、12 current member 全释放、12 schedule off、第三继任者路由/Runtime/claim gate/业务计数不变；verification 落盘并提交。
4. 下一波才构建 12 条新 selection/control/binding；本波不创建 definition，不开调度，不读商城源，不手工 Run。

任何权限、Receipt/定义、旧 Run、Host/资源、租户隔离或提交边界不明即停止写入。
