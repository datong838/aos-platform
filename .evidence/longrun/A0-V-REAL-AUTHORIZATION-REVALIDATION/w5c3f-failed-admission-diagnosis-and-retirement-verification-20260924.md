# W5c3f 失败 Prepare 只读诊断与正式退休验证（2026-09-24）

## 结论

**退休 GREEN，根因尚待安全观测。** W5c3e 失败安装 `82ec732b-51d6-4745-a871-57a2cd7848bc` 经原 Owner、全新键 `a0v-w5c3f-retire-failed-prepare-20260924-v1` 一次正式卸载，uninstalled/etag4/activeRevision null，`replayed=false`；九路/调度仍关闭，Host PID15014 空载，无 attempt/canary，受控源 claim40、meta_schedule_run53 未变。

## 诊断证据

- 精确失败 operation `97d921ed-579b-463e-ba2b-0cfccc9d8fb6` 的三个 resource lease 均 `create_claimed_at IS NULL`、container_id null、released/observed；正式事件是三个 `resource_intent_cancelled` 后 `preparation_failed`。Docker 中无新增运行容器。
- 以与 Host 相同的 credential/bundle/trust/context 构建原只读依赖，对 composition lock 的三项 runtime release 分别运行原 `load_record`、`admit_runtime_artifact` 与 `RegistrationDescription`，全部 GREEN；OCI isolation、签名 image digest/cache 均通过。Runtime 角色对 resource/operation 的 SELECT/UPDATE 权限只读检查通过。无资源 claim 的失败仍未有可归因的异常类型；不能推断为 Docker/签名/权限已完全无问题。
- 方案 `8402dcb6`；精确失败/释放/空载/九路/调度预检通过，0600 intent/result 与新 key Command 唯一。独立 audit 再核历史 operation/资源、正式卸载状态、activeRevision null 与业务计数不变。包装测试 1 passed、`git diff --check` 通过。未读商城源、未重发 prepare/verify、未启用业务。

## 下一波 W5c3g

先方案，给原 Runtime Host 的 prepare 失败路径补**仅异常类型与代码位置**的安全诊断（不记录异常值、frame locals、artifact/凭证/源数据），定向测试隐私与失败语义不变；安全重载唯一空载 Host。随后才另波创建全新 predecessor-free installation 并单次自然 prepare，以新证据定位真实故障。若可在只读范围证明更具体根因，优先直接修复并测试，避免多一次失败安装。
