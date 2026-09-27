# W5CB4 E06：数据源登记禁自动源读与未知结果冻结计划（2026-09-28）

## 上位与目标

承接 E05 和 231-9 BG-00/01/02。当前卷无 source config、正式商品对象与事件；`/v1/sources` 已是会持久写 `meta_source` 并由 DB 触发器记配置版本的既有入口，不能再造第二 Owner。本波修复 `DataPage` 当前产品动作的两个断点：通用 `apiPost` 可能离线排队；保存后自动执行 `/test` 读取商城源库。只修产品交互安全，不连接/读取真实源、不启用同步。

## 文件级清单与前哈希

- `apps/web/src/pages/DataPage.tsx`：`0b9b6ea13da29c6974c2291b04d7443b5c0490c2`。改为 `apiPostUnqueued`，提交前权威只读回读同 ID/期望修订，提交前存 tenant-scoped 待对账标记（仅 ID、运行模式、期望修订，**不存连接密钥**）；任何网络/写入未知、回读不一致均冻结。页面重开及租户切换时恢复对应 tenant 的 pending；写入期间固定 marker key，不可读 marker 失败关闭。只有**同次 POST 明确响应的配置修订**再由 `/v1/sources` 权威读回一致，才自动解除。未知响应时只读 GET 可诊断，单靠同 ID 不能独立证明是原请求，故仍冻结、不重发。删除自动 `POST /test`，不读取源表目录；保存成功仅展示“已登记、未测试、未同步”。
- `apps/web/src/pages/DataPage.source.interaction.test.tsx`：`c51151f684a535dd7b736448e811f4362a3dc299`。更新正/负例：离线队列禁入、保存后无 probe、读回漂移冻结、跨刷新 pending 与只读对账、marker 不含密码。相关 `Wave3bW4Truth.test.ts` 和 `sourceSetup` 邻接运行但无意改动。
- 不修改 `wave_ext.py`、`meta_source` 与迁移；服务端既有写入口并无新幂等 Receipt，因此 UI 不能提供“重试创建”按钮。未来若需要重试，先在 Owner 层新增正式 Receipt/未受理证明，不通过清 localStorage 规避。

## 验收和边界

先专项与邻接，再 TypeScript/production build、浏览器 `/data` 安全空态和当前服务重启后验证。不会输入 SSH/DB 密码，不执行 `/test`，不会把已有 12 数据集伪装成 Product。E06 只保证未来用户获准登记时不会因网络抖动重复创建/暗中读源；BG-02 自然触发仍待当前源正式配置和独立准入。未知结果、旧 12 Run、Host/worker/Provider 继续失败关闭。
