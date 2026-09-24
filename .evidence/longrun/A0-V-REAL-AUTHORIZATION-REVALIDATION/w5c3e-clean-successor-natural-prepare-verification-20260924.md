# W5c3e 干净继任者自然 Prepare 验证（2026-09-24）

## 结论

**FAILED，已冻结；未发 verify。** 唯一 `runtime-apply` 请求以新键 `a0v-w5c3e-clean-successor-prepare-20260924-v1` 被原 Owner 接受，operation `97d921ed-579b-463e-ba2b-0cfccc9d8fb6` 自然消费至正式 `failed`/phase `preparing`/revision7/`PREPARATION_EXECUTION_FAILED`。安装仍 approved/etag3、binding0；三个资源均 released/observed。不得重发此键或在此安装上再 prepare。

## 证据与已排除范围

- 方案 `1a2472a4`；请求前新安装 `82ec732b-51d6-4745-a871-57a2cd7848bc`、精确 lock `sha256:820eb34977f56544428e3ecde4fbbca637d6a8ad9cdbd66d223cbf35d58f7380`、Host PID15014 空载、九路 legacy/fenced、12 schedule off、budget rev13 有效、canary0；新键原生 Command/runtime operation0。0600 intent/result、单次请求、`replayed=false`。
- 正式事件序列 accepted→validating→preparing→三个 resource_intent_cancelled→preparation_failed；Host 仍为 PID15014 ACTIVE、liveTargets 空，没有因本次失败退出。Docker PATH 故障与本次不同：精确 PATH 下 Docker info/OCI isolation 检查通过，三个签名 image index 的 linux/arm64 config/image digest 均在本地缓存且 `require_cached_image` 只读通过。当前日志/正式事件不包含更深层异常类型，故本次具体失败点仍未知，不应猜为镜像缺失。
- Docker 中没有新增运行容器；安装无业务 attempt/canary。定向包装测试 1 passed，`git diff --check` 通过。未读商城源、未启用九路或调度、未手工触发业务 Run。

## 下一波 W5c3f

先只读定位失败阶段：精确资源 journal/container 留痕、原 Host 日志、受控异常可观测性与 Session/OCI 创建或握手边界；不得用再次 prepare 作诊断。随后按原 approved-uninstall 门禁正式退休本次失败安装；若需修补异常可观测性/Host，先方案、定向测试和独立 Host 重载，再创建全新 clean successor。未知提交边界一律冻结。
