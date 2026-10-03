# s3o-w-af 第一切片｜真实 macOS Unix peer 负例验证

## 实施与过程

- 先读 231-9/产品方案、D-wave、632、现有 `aip_network_issuer_ipc.py` 和私有 listener；文件级 plan 先落盘。只新增 `test_aip_bi_plan_issuer_ipc.py` 的真实 AF_UNIX 错 UID 用例，没有修改生产逻辑或当前数据库。
- `sudo -n -l` 明确 `sudo: a password is required`。测试不使用 monkeypatch；以当前 issuer UID 创建 0750 目录/0600 测试占位凭据，配置不同的预期 API UID，真实客户端仍为当前 UID。内核 `getpeereid` 不匹配，服务在读取帧和 dispatch 前关闭连接，handler 调用0，listener 退出后 socket 清理。
- 初次 RED 为 macOS AF_UNIX 长路径 `ISSUER_LISTENER_START_FAILED`（原 pytest tmp 路径超限）；改一次性短 `/tmp` 路径后，第二次 RED 是 `/tmp` 默认 wheel gid 与严格 ipc gid 不符；只在测试目录 `chgrp` 到当前 gid，保持生产路径校验原样。未放宽门禁。

## 本次输出

| 检查 | 输出/退出码 |
| --- | --- |
| `pytest -q ...test_aip_bi_plan_issuer_ipc.py ...test_aip_bi_plan_issuer_process.py ...test_aip_network_issuer_ipc.py` | 39 passed，退出0 |
| `python -m py_compile`、`git diff --check` | 无错误，退出0 |
| 当前库只读 | `aos_current_preview_20260927@a0v_135`，正式 `aos_bi_plan_issuer` 角色0，正租户 Plan0；未写当前库 |
| 正式 OIDC 预检来源 | 本进程 `AOS_OIDC_ISSUER`、`AOS_OIDC_JWKS_URL`、`AOS_OIDC_AUDIENCE` 均未配置；代码要求 external-only、https、非本地地址。没有读取或输出任何凭据值 |

## 结论与下一门

真实内核 **错误 UID 负例 GREEN**；不同 OS UID 正向仍未证明，不能用本测试或合成 peer 放行正式私有进程。正式 IdP、角色/凭据、role→scope+subject、六 active Agent 和当前库安全切换也未齐；该实例保持失败封闭。下一步在合法不同 UID 环境核正向，再做断联/错租户/失凭据组合；若环境身份不可得，推进已登记 Tool/八配置独立安全项。Host/worker/Provider保持关闭。
