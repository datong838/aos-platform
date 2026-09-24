# W5c3b 新继任者 Prepare/Verify 验证（2026-09-24）

## 结论

**FAILED，按计划冻结；未执行 verify。** 已批准 installation `ae42f0e5-270a-4b7b-8a82-fd3bfbb925dc` 的唯一 `runtime-apply` 请求返回 operation `b5175270-7de4-4608-b6aa-6a9713b66845`，幂等键 `a0v-w5c3b-successor-prepare-20260924-v1`。原 Host 自然消费后 operation 正式终态 `failed` / revision 7 / `PREPARATION_EXECUTION_FAILED`；不得重发同键，不得将 approved 当作 prepared，不得提交 runtime-verify。

## 证据与故障边界

- 请求前 approved/etag3、无 binding/resource/operation、Host PID 14022 ACTIVE 且 liveTargets 空、九路 legacy/fenced、12 schedules disabled、canary0。intent/result 为私有 0600 文件。
- Host 的私有 status 记为 `SAFE_BLOCKED` / `HOST_RUNTIME_FAILED`，错误链在 `extension_runtime/oci_driver.py:25` 的 `subprocess.run(["docker", ...])` 落到 `FileNotFoundError`。launchd job 随后退出，`launchctl list` 为 `- 2 com.aos.a0v-w5c3-runtime-host`。Plist PATH 缺少 Docker CLI 实际所在 `/Users/ddt/.docker/bin`；这是根因判断，不把路径修复等同于 runtime 成功。
- 只读安装快照：仍 approved/etag3、binding0，唯一 operation 正式 failed；三个 resource lease 均 `released` 且 `observed_release=true`。Docker context 中只有原有三个 PostgreSQL 容器，没有新增运行容器。受控源 claim=40、meta_schedule_run=53、未终态 runtime operation=0、新 installation attempt=0、canary installation=0。
- 定向测试 `AOS_DOTENV_DISABLED=1 PYTHONPATH=scripts ... pytest test_a0v_w5c3b_successor_lifecycle.py` 为 3 passed；脚本保留单次请求和严格 preflight/观察门禁，但实际执行未达到 plan 的 prepared/verify 成功出口。未读商城源数据，未启用九路或调度，未触发业务 Run。

## 下一波 W5c3c

先方案并复核原 `preparation-reset`/direct successor 合约。已释放资源不可复活；本次失败的 approved installation 不在 W5c3b 内重试。修正独立 Host 的 Docker PATH 并验证空载健康后，依正式 Owner 退休/重建可用继任者，再按新 intent/key 执行下一波 Prepare/Verify。每个请求均须单次、自然消费、终态和真实同进程 PreparedJob 读回，未知边界冻结。
