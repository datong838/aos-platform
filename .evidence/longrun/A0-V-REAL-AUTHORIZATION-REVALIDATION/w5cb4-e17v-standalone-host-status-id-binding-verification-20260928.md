# W5CB4 E17-v｜独立 Host 状态精确 ID 绑定 verification

## 最小变更

`scripts/a0v_ecommerce_runtime_host.py:_current_preflight` 消费 E17-l 的真实只读报告，仅接受精确 GREEN outcome、`PREFLIGHT_ONLY_NO_RUNTIME_START`、`org-org/dev-project` 和符合数据库 Host ID 约束的 `hostId`。内部 `_serve` 必须显式取得 `current_host_id`，在任何环境配置前验证；运行状态使用该 ID，不再写 2026-09-12 历史常量。CLI `main` 即使得到经验证 ID，仍固定 `FORMAL_OWNER_AUTHORITY_UNPROVEN`，没有进入 `_serve` 的生产路径；不提供用户可随意填写 Host ID 的命令参数。

## 证据

| 检查 | 命令与结果 |
| --- | --- |
| RED | `python -m pytest -q -o log_cli=false services/aos-api/tests/extension_runtime/test_a0v_ecommerce_runtime_host.py -k current_host_id --tb=short`：退出 1，4 failed，旧代码无报告 Host ID 验证。 |
| GREEN 专项 | 同文件全跑：退出 0，29 passed；含空/跨租户/非精确报告拒绝、缺 ID 在配置环境前拒绝、内部测试状态使用 `current-host`。 |
| 邻接累计 | Host CLI 测试加 runtime connections、E17-l preflight、production runtime、UI wiring、startup composition、installation API 和 current preview：退出 0，142 passed。`compileall`、`git diff --check` 退出 0。 |
| 当前真实边界 | E17-u 只读当前库：Host identity=[]、精确 Host assignment=0、runtime operation/binding/configuration 0、Action approval/receipt 0；E17-l 无法产生正向 `hostId`。当前签名预览 API 8080/8434 可达、Host disabled、18181 无监听；本波没有启 Host 或触碰当前库。 |

## 复审与下一波

实现仅消除错误状态 ID 来源，与方案一致；没有解除 Owner/Approval/Receipt 门。`LiveInstallationLifecycleOwner` 是 runtime operation 之后构造的进程对象，不能当启动前人工授权。下一波需复习 231-3 产品链并定位正式 Host identity/assignment、三身份、配置候选及批准/预算的合法供给；仍缺外部正式凭据时推进独立代码项，不用旧账号/旧 Host ID/假 ApprovalRef。浏览器 `browser-pilot` 无新截图，首链未完成。
