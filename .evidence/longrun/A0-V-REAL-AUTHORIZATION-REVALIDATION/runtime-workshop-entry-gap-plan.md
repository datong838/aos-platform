# AR2 N7/N8 真实前端交付缺口与衔接计划

基线96a7b605，2026-09-13主库只读及IAB核验。当前安装97aeb2e7-59ba-40f6-89a3-fb0293bc0497锁定domain.ecommerce.core1.3.0、platform.ecommerce.niushop1.5.0、solution.ecommerce.growth1.7.0、operations-base1.2.0，注册内容hash与安装锁完全一致。四包均无runtime.frontend；资源origin亦未配置；当前catalog返回0项。详见runtime-workshop-entry-gap.json。

## 判断

旧PostgresWorkshopCatalogSource在replacement图选定后用legacy_content_predicate排除含runtime的锁，防止active安装被当作业务授权。保留此约束。RuntimeUiSessionResolver需一个签名前端manifest及可信resource origin，当前条件不具备。现有EcommerceWorkshopHost内仍有八页静态实现和原HTTP客户端；把菜单放开会绕回旧业务路径，不能作为运行时领域包交付。

## 衔接原清单（新增验收工作，不另立业务系统）

| 原项 | 增量工作 | 退出证据 |
|---|---|---|
| N7 平台宿主 | 首次切换全阶段当前权限、exact审批、原键回读和产品入口 | 真实9项注册的精确切换链；未知结果不重发 |
| N7 运行时目录 | 新的运行时目录投影绑定当前安装/代次/纪元、签名Release、权限与已声明route，不放宽legacy谓词 | 未安装/禁入/撤权/旧代次不可见或不可执行，正租户与canary隔离 |
| N8 前端交付 | 将工作台前端作为签名包资源构建，界面数据与命令只经受控桥接，不携带主站凭据、不直连旧领域HTTP | artifact hash、CSP/nonce/source校验、read/command claims、禁入及卸载重装实测 |
| N8 八场景 | 优先经营参谋→exact计划评审→内容承接→评审续跑→总控Wiki，再扩客户/创作者/媒体/价格/经营管理 | 每场景实际数据来源、Case/Run/产物/评审与Receipt完整；随后连续观察 |

实施前必须解决的合同：当前UI resolver只接受一个frontend候选，growth与operations-base的路由归属不能靠任意扩大claims合并；前端入口组合应遵守当前安装组合贡献，而非复制八份平台页面。新增read操作需注册到签名后端并核验当前权限，不能通过通用任意SQL或任意URL桥接。现有版本不能原地修改；构建新版本、现有Registry/Installation流程交付，当前9项登记与原Receipt保持历史。

下一波先完成N7切换写入口前的当前权限门，包含幂等回放也重新鉴权；随后确定N8前端桥接读合同与新包版本交付，不能把这一审计文档当完成实现。230 L0不在本增量范围，仍挂起。
