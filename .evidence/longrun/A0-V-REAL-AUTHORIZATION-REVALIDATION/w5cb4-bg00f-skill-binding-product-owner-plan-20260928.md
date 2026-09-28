# W5CB4 BG-00f｜现有 SkillBinding Owner 的首段产品入口方案

## 上位合同与当前边界

231 首链与 AIP-6 BIND-3 要求 Skill 先正式发布，随后组织侧创建、评估并激活 exact SkillBinding，Receipt/租户/预算/就绪门由后端 Owner 判。`routers/aip_bindings.py` 已有 `/v1/aip/skill-bindings` 的 list、preview、create、evaluate、activate 等入口；`AipSkillRegistry.create_binding` 仍检查 exact published 修订、publication tenant、实例、必需能力与幂等 Receipt。当前 D01@1 仅 evaluated，当前库 SkillBinding/活跃 CapabilityBinding/预算策略均 0，本波不得对当前库 POST。

## BG-00f-a 文件级第一刀：精确只读候选编译器

先改 `apps/web/src/api/aipAgentControl/skillBindingCandidate.ts` 与同名测试。输入只接受当前 Registry 角色快照、完整 published Skill 修订、其精确 RuntimePolicy 和当前租户 CapabilityBinding 快照；输出仅为供后续 Owner 创建命令使用的候选或具体阻断码，不在当前实例触发 POST。必查 Skill 与角色目录同 revision/hash、publication tenant、policy revision/hash 与预算引用、必需 Capability 一一对应且 active/available/新鲜、无重复候选；任何未知/跨租户/漂移均返回不可提交。测试先 RED 再实现，专项、TypeScript 与 diff check。编译器输出不等于后端授权，创建时原 Store 仍重验。

## BG-00f-b 后续产品创建入口

1. `apps/web/src/api/aipAgentControl/`：增量增加当前 published Skill 列表、精确 RuntimePolicy 读取及 SkillBinding create/get 的严格租户与 hash/Receipt 回读。所有写调用使用不排队的命令 API；未知结果在客户端保存原 idempotency key 及请求身份，先只读对账，禁止换键重发。
2. `apps/web/src/pages/s2/CanonicalAgentRegistryPage.tsx`：在有已安装实例时展示“配置技能绑定”首段；只从已发布 exact Skill、当前活跃且唯一的必需 CapabilityBinding 和 Skill 所指 RuntimePolicy 的 exact `budgetPolicyRef` 形成候选。当前缺任何来源时展示缺口并禁用提交；不提供自由文本 ref 或默认预算。人工确认后创建 provisioning Binding，回读同租户 exact binding 与 Receipt；本波不自动 evaluate/activate 或启动 Run。
3. 对应 SDK 与页面测试先 RED，覆盖当前 D01 evaluated 禁入、跨租户/漂移/重复能力/缺预算拒绝、未知结果不重发、正向构造和 Receipt 回读。仅测试环境用模拟响应，真实验收仍需当前正式来源。跑专项、邻接累计、TypeScript、diff check；浏览器 pilot 不可用则记录缺口。

## 后续

BG-00f 下一刀再接 evaluate/activate 的显式预览与确认，保证 Owner 新鲜依赖快照、版本 CAS 和 Receipt；D01 真 Eval Dataset/Case/Judge/执行器仍独立补齐，不因产品入口可用而解禁。
