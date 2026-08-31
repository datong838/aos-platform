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

## 内置浏览器补充验收（待两页证据闭合）

2026-08-31 已从完整侧栏逐页进入生产合同、专业能力、智能体注册表、智能体市场、智能体列表、Skill 发布、智能体导入、能力导入 8 个页面，并执行了滚动、筛选、选择、页签、详情与侧栏折叠/恢复检查。恢复核验时重新审阅原始截图发现：生产合同、专业能力、智能体注册表、智能体市场、智能体列表和 Skill 发布 6 页为加载完成画面；智能体导入、能力导入的顶部/底部 4 张截图均为空白帧，不能作为页面已加载证据。因此本节不再把 8 页整体记为浏览器封板完成。

- 生产合同：读回 8 份任务简报、8 份评测合同、2 份责任计划、2 份阶段模板、1 份影响预览和 1 份执行提案；未把缺失 EvidencePack 或 StartDecision 显示成 0 业务量。
- 专业能力：读回 10 项定义、48 项组织绑定、12 项活动绑定和 41 项技能绑定；逐项显示 Provider、Route、Eval、Health、Tool、Data、Policy 依赖，不用统一“未就绪”代替诊断。
- 智能体目录、市场与列表：读回六数字同事、37 项 Skill、10 项能力和安装包，点击市场详情及实例“工具箱 / 试运行 / 发布”页签后内容均发生可观察变化。
- Skill 发布：读回 39 项技能、80 条修订；切换已发布筛选并选择第二项技能后，详情标题、精确证据与绑定入口同步更新；没有点击发布命令。
- 导入页：此前 DOM 检查读到 Agent/Capability 的来源、摘要、许可证、签名、SBOM、依赖、映射、风险、网络、opaque SecretRef 与 schema 字段；但现有截图为空白，必须在内置浏览器重新连接后补拍加载完成画面并复核主内容滚动，才可作为封板证据。补拍前不得生成新预检、创建 ImportJob 或执行外部下载。
- 侧栏：折叠后可恢复，恢复后仍可读智能体市场、记忆治理及模型管理入口；8 页均未丢失完整导航。

本次浏览器操作仅包含 GET、筛选、选择、页签、详情、折叠/恢复与滚动；Provider 调用、Secret 解析、正式安装/激活/发布、经营系统写入、外部副作用和 Release 均为 0。自动化、真实租户控制面 Saga 与负向租户隔离证据保持有效；P4 仍需补齐两张导入页加载完成后的顶部/底部证据并确认页面日志无 error，之后才进入 Delivery Receipt 与 authority CAS 收口。
