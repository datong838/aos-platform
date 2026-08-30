# AIP-P4 智能体生产生命周期验证记录

## 边界

- 租户：`org-org/dev-project` 为真实开发租户；`dev-org/dev-project` 仅作隔离负向验证。
- 允许：AOS 控制面草稿、预检、ImportJob、可逆候选和 Receipt。
- 禁止：解析 SecretRef、调用 Provider、激活正式实例、写经营系统、真实发布或 Release。

## 已闭合自动化证据

- Web：单线程全量 Vitest 退出码 0；此前并发资源争用产生的 14 个失败点按 4 个文件单线程复跑为 39/39 GREEN。
- Web：生产构建退出码 0，`built in 16.27s`。
- API：AgentRun、ImportPreview/ImportJob 与迁移专项累计 15/15 GREEN。
- API：P4 与路由清单累计 23/23 GREEN；路由清单 8/8 GREEN、2 个子测试 GREEN。
- OpenAPI：确定性导出与兼容门 16/16 GREEN；2718 个路径、4514 条路由记录、4504 个唯一操作。
- Python：`compileall` GREEN。
- 迁移：`aip_p4_001 (head)`，共享开发库 current 与唯一 head 一致；迁移专项覆盖升级、降级、RLS 和运行角色授权。
- 运行态：API 精确运行所有权通过，`/v1/health` 返回 `ok`，`/v1/ready` 返回 `ready`，Web `:5173` 可达。
- 真实开发租户控制面验收：`org-org/dev-project` 已完成 Preview → ImportJob → 审批 → 内部候选 → exact readback → 补偿回滚；Job `aip-import-115e74fa308d40858cfb98d6585250cd` 最终为 `rolled_back`，候选最终为 `rolled_back`。
- 租户隔离反证：同一 Job 由 `dev-org/dev-project` 读取返回 404；全过程 Provider 调用、经营系统写入、正式激活与 Release 均为 0。

## 产品闭环

- 生产合同按业务场景聚合，支持生效修订、依赖、消费方、exact ref 与来源深链。
- 能力与智能体注册表展示角色/能力缺口、同截止面依赖与安全派发证据。
- 市场、实例和 Skill 页面补齐来源、许可证、兼容性、运行质量成本、发布/绑定/回滚与消费方追踪。
- Agent/Capability 导入形成 Preview → ImportJob → 审批 → 可逆候选 → 读回 → 精确回滚 Saga；所有变更使用租户、RBAC、幂等键、版本 CAS 与 Receipt。
- 真实租户验收使用低风险、内容寻址的栖月汇内部能力包，仅验证 AOS 控制面治理链；Preview 如实保持 `external_required`，审批不等于外部测试已完成，回滚后没有残留可运行候选。

## 尚未冒充完成的证据

2026-08-31 本轮连接内置浏览器时，可用浏览器列表为空。因此没有生成伪造截图，也没有用独立 Playwright 代替。P4E 必须在内置浏览器恢复后逐页从完整侧栏进入以下 8 个页面，滚动、点击、读回并保存三视口证据：生产合同、专业能力、智能体注册表、智能体市场、智能体列表、Skill 发布、智能体导入、能力导入。

在该证据闭合前，P4 总清单保持未勾选，authority 和 Delivery Receipt 不宣告 P4 GREEN。
