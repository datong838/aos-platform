# AR1-c 职责引用与配置组合检查点

日期：2026-09-06

本检查点将 `ConfigurationDocument.roleRefs` 的首个正式 authority 固定为 `aip.responsibility_plan_revision`。AIP 适配器在调用者同一显式事务中要求 `aos_runtime` 和精确 TenantScope，锁定当前 responsibility-plan head，重建原 `CreateResponsibilityPlanRequest` 并校验 canonical hash，仅接受当前、精确且 frozen 的职责计划。

新增的 AIP 正式组合工厂只注册职责计划、数据分类、预算和运行策略四类已知 authority；未知 authority 无通配或默认 True。预算原 DTO 显式转为严格布尔判定。职责计划准入不授予 assignee、capability、dispatch、approval 或费用权限，任务开始仍由原权威重验。

验证：专项 42 passed；相邻配置/职责/启用 178 passed；累计 extension-runtime 与既定 asset-registry 安全集 833 passed、6 warnings、134.50 秒、exit 0。包含旧 head、非冻结、结构化列与哈希漂移、特权连接、跨租户和另一连接无法越过 `FOR SHARE` 改写 head 的反证。`git diff --check` 与编译通过。退出时既有 JDBC 日志 closed-stream 噪声仍在，缓存计数0，不改变测试结果。

独立 Prime 复审结论：未发现确定性代码阻断。下一波已吸收两项增强：用非空 W6 治理字段的职责计划正例/漂移反证；用四个真实 reader 贯穿一次签名安装→配置→启用准入。

边界：仅使用 `127.0.0.1:18432` 专用临时 schema；无共享迁移、真实业务数据修改、Provider、费用、发布或页面变更，浏览器验收不适用。业务场景仍为 0；AR1-c 仍在进行。
