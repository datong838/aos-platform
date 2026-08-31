# P6C-A 容量池与 Usage Receipt 权威验收

## 结果

`AIP_P6C_A_CAPACITY_USAGE_RECEIPT_CODE_BROWSER_GREEN_NO_EXTERNAL_EFFECT`

- 用量仪表盘已停止读取旧的兼容 usage 列表，今日、近 7 天、近 30 天均只从租户域 Usage Receipt 汇总。
- `org-org/dev-project` 当前近 30 天可回读 16 条实测 Receipt、2046 个输入 Token、882 个输出 Token，并能按三个 Provider 解释；今日和近 7 天没有 Receipt 时显示“未观测/缺少凭证”，不伪装成 0。
- 预留容量页只展示 canonical overview 返回的 exact CapacityPool，包含并发、单次租约用量、租约时长、生命周期和安全处置入口；已删除静态 20% 与“未开通”占位。
- 兼容项目/用户限额保持只读，写入口统一指向版本化运行策略；不存在权威预算或 Usage Receipt 时不再渲染 `$0` 或 `0%`。
- 速率限制展示使用 `tokenUnitPerReservation`，不再把池总容量 `maxTokenUnits` 冒充单次租约用量。

## 专项与累计验证

- API 合同、周期汇总、调整、租户隔离与 OpenAPI：18/18 GREEN。
- Web parser 与容量页纯逻辑：49/49 GREEN。
- TypeScript `tsc --noEmit`：GREEN。
- Web production build：365 modules transformed，GREEN；仅保留仓库既有大 chunk 提示。
- `git diff --check`：GREEN。

## 运行态只读探针

- `GET /v1/aip/model-runtime/cost-overview`，租户 `org-org/dev-project`：HTTP 200。
- `today`：0 条 Receipt；页面语义为“未观测”，不是业务量 0。
- `week`：0 条 Receipt；页面语义为“未观测”，不是业务量 0。
- `month`：16 条 measured Receipt，`input_token:token=2046`、`output_token:token=882`；Provider 计数为文本 12、图像 2、视频 2。

## 浏览器验收

- 中断前已在内置浏览器打开 `/aip/capacity`，逐页签检查“用量仪表盘”和“预留容量”。
- `p6c-usage-month.png`：完整 AIP 侧栏可滚动；用量页明确显示今日 Usage Receipt 未观测，没有缺证归零。
- `p6c-capacity-pools.png`：容量页消费 exact pool；静态 20% 与“未开通”已移除。
- 本次恢复时浏览器运行时未暴露可用标签页；没有用源码检查冒充新的浏览器证据，也没有改用不受授权的浏览器表面。已有截图的 SHA-256 已单独核验。

## 安全边界与剩余子包

- 本包只闭合 P6-108、P6-109；P6-106 的 Agent/Logic/模型/任务归因与 P6-107 的 RPM/TPM/并发/预算版本化配置在 P6C-B 继续施工。
- 未调用 Provider、未生成内容、未切换流量、未写真实业务数据、未修改迁移或发布状态。
