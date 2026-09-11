# Ecommerce Runtime Host 与 growth 1.4 preparation 验证

日期：2026-09-12

## 结论

- Host bootstrap 与重放通过：三个非特权 LOGIN 主体、一个正租户 assignment、零负租户 assignment；Identity/Assignment 重放后均保持 revision 1。
- 三个真实连接主体同库、互异、非 privileged、非 protected relation owner；Directory/Runtime/Web membership 分别为 directory-only、runtime-only、none。
- 独立 Host selector 达到 ACTIVE，诊断 API 继续保持 Host disabled；Host 仅发现 `org-org/dev-project`。
- 单用途 Runtime Owner 通过持久成员目录取得 `admin`，负租户为零；过期且从未 claim 的 v1 apply 由既有 `fail_uncommitted_preparation` 收口为 `PREPARATION_EXPIRED`。
- v2 apply 通过签名、当前成员权限与 claim，进入 `preparing` 后由 exact registration 拒绝，并终结为 `PREPARATION_EXECUTION_FAILED`。三个 resource lease 均为 `cleanup_state=released`、`observed_release=true`，Docker 无遗留 extension container；Installation 保持 revision/etag 3、activeRevision null。
- 根因是已发布运行包的后端注册 1/2/9 个 API，但签名 Manifest 未声明这些 API。不得放宽 exact registration 或修改已发布字节；后续按方案发布新坐标并重新首次安装。

## 自测

- Host bootstrap 单测：7 passed。
- Host/production wiring/RuntimeHost 组合回归：49 passed。
- 1.4 activation/lifecycle 单元回归：33 passed；PG opt-in 用例未在这条命令启用，真实隔离库运行证据由本目录 JSON 提供。
- Python compile 与 `git diff --check` 通过。

## 证据

| 文件 | SHA-256 | 说明 |
|---|---|---|
| `runtime-host-growth-1.4-attempt/host-bootstrap-apply.json` | `b1b14df4849d77cc7c1c4713302aebd5d3d8aa4b4c3407fb4d863ecc39b269c7` | Identity/Assignment apply |
| `runtime-host-growth-1.4-attempt/host-bootstrap-replay.json` | `13f250b106327508cee350ba9f675c6b89165e449805a491ba4c7f7ad40400ce` | revision 不增长重放 |
| `runtime-host-growth-1.4-attempt/host-identity-probe.json` | `1e0cc4e5326efde519eeb34b4867206ecac1b7e876fde105da79008fab9c2fce` | 三平面真实连接探针 |
| `runtime-host-growth-1.4-attempt/host-terminal-status.json` | `8c4a47bdc486bf44320caa2cd2cdf19a539d94ac36d0026243f65ed747f68240` | Host fail-closed 终态 |
| `runtime-host-growth-1.4-attempt/terminal-database-state.json` | `9882e4bcdbc5175900f8f43d0a427545ea026a6ccb5ee89d5cea671d9bcbcd67` | Operation/lease/membership/Installation 终态 |

凭据文件只留在仓外 `0600` state；证据中没有 DSN、密码或明文密钥。本波 Provider 调用 0、业务 Operation 0、外部发布 0。
