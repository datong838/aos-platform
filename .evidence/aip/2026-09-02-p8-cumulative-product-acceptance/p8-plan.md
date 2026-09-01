# AIP-P8 累计产品验收实施方案

> Task：`AIP-P8-CUMULATIVE-PRODUCT-ACCEPTANCE`
> Authority 基线：`AOS-000447`
> 代码基线：`m1@6b843d87`
> 正向租户：`org-org/dev-project`
> 负向隔离 canary：`dev-org/dev-project`

## 1. 上位方案与边界复习

本波只闭合总控清单 AIP-P8-125～132，不把历史测试、静态截图或方案状态外推为产品完成。验收必须从页面可见行为反向追溯到前端请求、服务端合同、数据权威与 Receipt/Lineage，并保持租户隔离和失败关闭。

允许：本地开发环境中的只读查询，以及有精确租户、版本和 Receipt 的受控配置写入；发现缺陷后在本波方案范围内最小修复。

禁止：Provider 调用、密钥解析、真实客户触达、真实业务发布/改价/发送、数据库迁移、外部副作用和 Release。`plugins/ops` 不在本波写范围。

## 2. 文件级施工与验收包

| 子包 | 清单 | 主要文件/证据 | 完成定义 |
|---|---|---|---|
| P8A 菜单与控件矩阵 | 125、126 | `apps/web/src/shell/AppShell.tsx`、25 个 AIP 页面、共享页面组件与测试、`p8-page-matrix.json` | 25/25 从真实侧栏进入；侧栏/主区滚到底；分组与整体折叠恢复；页签、筛选、选择、详情、保存/取消、刷新、错态恢复与 exact 深链均有实测结论，发现缺陷即修复 |
| P8B 合同追溯 | 127 | `apps/web/src/api/`、`services/aos-api/aos_api/routers/`、领域 service/store/contract、`p8-contract-trace.json` | 每页记录页面 owner、请求、服务端 handler、权威来源、Receipt/Lineage；缺失引用失败关闭，不用 traceId 代替 lineageId |
| P8C 双租户业务场景 | 128、129 | 六数字同事、AIP 分析师、文档智能页面/API 测试与浏览器证据 | `org-org/dev-project` 只消费当前真实事实并完成允许的受控写回读；`dev-org/dev-project` 不可见、不可写、跨租户深链失效；不写真实业务数据 |
| P8D 累计质量门 | 130 | Web/API 测试、TypeScript、生产构建、`git diff --check` | 专项、API 累计、Web 全量、类型检查、构建和差异检查全部 GREEN |
| P8E 视觉与可访问性 | 131 | Codex 内置浏览器截图、`p8-viewport-accessibility.json` | 1280/1440/1920、200% 文本、键盘/焦点逐页抽检；无顶部挤压、遮挡、死控件、菜单丢失、文档级横溢或双滚动陷阱 |
| P8F 交付闭环 | 132 | 本目录 verification、Delivery Receipt、Git、authority、memory/Prime | 方案/代码/证据一致；安全提交；CAS、sync/validate/gate 与 Prime exact readback 全部闭合 |

## 3. 串行执行顺序

`P8A → P8B → P8C → P8D → P8E → P8F`。每个子包都按“复习上位方案→最小实现/修复→专项测试→累计回归→浏览器验收→一致性复审→证据更新”执行；普通子包闭合不是停点。

## 4. 风险控制

1. 当前工作树中 P6D 验证文档、`ModelRuntimePage.test.tsx`、`plugins/ops` 和历史未跟踪证据属于保护范围，P8 不覆盖、不混入提交。
2. 浏览器安全验收只点击只读或本地受控配置动作；可能触发 Provider、发布、客户触达或真实业务写入的控件只验证预检/失败关闭，不执行副作用。
3. 文档模板运行时状态若在服务重启后消失，必须如实记录其 authority/durability 边界；未经迁移门不得用数据库变更掩盖。
4. 只有同一 cutoff 的页面、API、authority、Receipt/Lineage 与双租户证据共同成立，才允许勾选对应 P8 清单项。
