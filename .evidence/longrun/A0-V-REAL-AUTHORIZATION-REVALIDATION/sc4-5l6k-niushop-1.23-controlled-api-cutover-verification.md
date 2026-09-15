# SC4-5l6k Niushop 1.23 受控 API 切换验证

日期：2026-09-15  
代码：`0d7e3ebd`  
范围：六步中的第 3/6 步。

产品受控 API profile 已从 1.22 current 签名根切到 `signed-bundles-niushop-1.23-current`。22 项 profile、P02 E preflight 和执行保护测试通过；所有关闭标志保持不变。

真实只读 `check` 返回 `CONTROLLED_API_LOCAL_DIAGNOSTIC_PREFLIGHT_GREEN`，明确 `sourceCalls=0`、`runsCreated=0`。旧 18181 PID 40240 的命令精确匹配 `a0v_product_controlled_api.py serve` 后收到 TERM，端口确认释放。新 PID 60292 使用同一受控启动器启动，`/v1/health` 与 `/v1/ready` 均为 HTTP 200。

新 API 与 Runtime Host 现在读取同一个 Niushop 1.23 签名根。API 内第二 Host、迁移、QYH Cron、AIP 自动任务、模型健康维护和 SSH 预热仍关闭；独立 Runtime Host PID 58194 未重启，三个 OCI 持续 running/network none。

不可变证据：

- `product-api-niushop-1.23-check.json`：SHA-256 `48d59074db48adc60c2f31a97f9a105b9e242514badcf02d76bbed5295b4ce5f`
- `product-api-niushop-1.23-serve.json`：SHA-256 `62982fead754c09ebdfd3016c6f779d8e3cfad02357a701989262f8e5f8674a6`

本步没有读取真实商城，没有创建 Run。下一步只允许使用已冻结的 E ScheduleBinding 触发一次 P02，finally 恢复 Schedule disabled；未知或失败结果不换 key 重发。
