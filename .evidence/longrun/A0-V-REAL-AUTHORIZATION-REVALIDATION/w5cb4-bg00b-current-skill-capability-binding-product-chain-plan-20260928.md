# W5CB4 BG-00b｜当前六实例的正式 Skill/Capability 绑定产品链

## 上位与现场

复习 231-1/9：数字同事复用 AgentInstance，同一租户单写 Owner；Skill/Capability 绑定、职责计划、预算、审批、健康与运行证据必须由当前权威逐项成立。已安装 ≠ 可派发，不从静态目录或旧代复制。当前 `aos_current_preview_20260927@a0v_111` 六 AgentInstance，SkillBinding/CapabilityBinding/ResponsibilityPlan Head 均 0；八运行配置候选均 0，Host 禁入。

现有 `aip_bindings.py` 已有 capability/skill preview、create、evaluate、activate、suspend/revoke、按 ID 回读；`CanonicalAgentRegistryPage` 目前仅只读展示绑定和安装/激活六实例，前端没有正式绑定创建流程。两个 preview POST 请求都由调用方提供完整 exact ref/dependencies；它们能复核已知来源，但不负责发现来源。`SkillPublishPage` 的 evaluated→published 对账存在，但当前发布候选依赖正式模型/评测/路由，不能以历史目录或假账号替代。

## 本波文件级计划：先修发布来源的可操作阻断

READ ONLY 当前库：37 个 evaluated Skill、0 个 published Skill、10 个 published Capability、6 个 AgentInstance、0 个 SkillBinding；同租户 release decision/publication event、Logic publication、ModelRoute Head、RuntimePolicy Head 均 0。`SkillPublicationOptionsReader` 因此对所有这些技能返回 `RELEASE_PUBLICATION_UNAVAILABLE`、`LOGIC_PUBLICATION_UNAVAILABLE`、`MODEL_ROUTE_UNAVAILABLE`。先做绑定 UI 会遇到空正式 Skill 来源，应后置。产品军规 `52-AIP前台中文展示军规.md` 禁止主文案裸露技术代码，现 `SkillPublishPage` 原样显示三英文 blocker，且缺 Logic/模型配置的直接可查入口。

本波只改两个前端文件，不写当前库、不发布 Skill：

1. `apps/web/src/pages/s2/SkillPublishPage.tsx`：把已知三种 blocker 映射为中文的当前缺口与合法下一步；Logic 提供现有 `/aip/logic` 入口，ModelRoute 提供 `/aip/model-router` 入口。发布放行证据没有确认能办理的产品入口时仅说明需正式放行及回执，不造可点的假按钮。未知 blocker 不吞掉，应显示保守的“权威阻断待核对”及审计代码 `<details>`；不把缺失候选变成 ready。现有“打开权威绑定流程”链接指向 AgentRegistry，但该页没有读取 `intent=bind` 或绑定创建 UI；改成诚实的“查看组织绑定状态”，不传无效 intent，并明确正式创建入口待接线。
2. `apps/web/src/pages/s2/SkillPublishPage.test.tsx`：先 RED，断言中文、两条真实路由、未知阻断保留、发布按钮 disabled、零 POST；相邻发布正向测试继续通过。TypeScript 与专项回归。

下一波再做 Skill/Capability 正式候选目录及绑定预检产品链：

1. 先定位现有正式 SkillTemplate/CapabilityRevision 当前可见目录是否能提供 exact ref、发布状态和依赖；若无，最小新增租户只读候选目录 API 与合同测试。目录不能把已评测 Skill 当已发布。
2. `apps/web/src/api/aipAgentControl/` 消费正式候选目录及 binding preview；`CanonicalAgentRegistryPage.tsx` 只允许选择当前来源，显示阻断，不手填任意 ID 或自动发布/保存。
3. 当前发布/审批/模型/预算/职责计划正向来源齐备后，另波通过真实 Owner 从产品入口创建/评估/激活精确绑定，做恢复/重装验收。绝不因目录数量或隔离测试替代当前正向。

## Write 前待复核

两个 preview 仅接受请求方 exact ref，不能误称为已发现候选。本波先让发布阻断与下一合法动作可见，不以 UI 代替来源生产。后续逐行读 create 合同、服务端 Owner 权限、正式目录及 RLS，才编码绑定段。此计划未授权当前库写入。
