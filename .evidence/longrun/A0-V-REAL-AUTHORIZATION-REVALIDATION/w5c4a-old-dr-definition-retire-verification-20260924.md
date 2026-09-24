# W5c4a 旧 DR 定义正式退休验证（2026-09-24）

方案 `04190ca2` 完成。旧 DR definition `446cc1ae-fa5b-406a-9446-d32104126dda` rev3 disabled/hash `sha256:48e236e8e5951defd0cb91cd9d52afc8bec287241804bd3202713ae03cfc22bd`、12 current member、53 历史 Run 无退休阻断、租户 admin/旧安装 active etag5、第三继任者 Resume 仍绿等预检通过。私有 0600 intent 固定唯一 key `a0v-w5c4a-old-dr-definition-retire-20260924-v1`。

原 `PipelineSnapshotScheduleDefinitionOwner.transition(intent='retire')` **一次**调用成功，经正式当前安装控制权限校验；旧定义 head rev4 retired，hash `sha256:2697f7021463feee31c8cc2b6b43aa99ba829ff87de7fd4c3c094af810502ecf`。独立只读审计 `W5C4A_DR_DEFINITION_RETIRED_GREEN`：唯一 rev4/key，12 个 current member 全释放，12 schedule enabled=0，第三继任者九路/Runtime/claim gate 不变、业务 claims40/runs53 不变。未卸载 DR、未直改表、未读商城源或手工 Run。

下一波开始建立第三继任者 12 条新 SourceSelection→RuntimeControl→ScheduleBinding 链；必须使用现行四来源/预算/图/源配置的正式 Owner 校验和新有效窗，旧 DS 控制链不可复用。新定义配置/启用仍独立后续波。
