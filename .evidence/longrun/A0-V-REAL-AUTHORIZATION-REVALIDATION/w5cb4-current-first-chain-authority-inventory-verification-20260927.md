# W5CB4 当前首链最小权威只读盘点 verification（2026-09-27）

## 第 1/9–3/9 步：Rules、上位方案、文件级范围

接续 `w5cb4-current-governed-binding-route-plan-20260927.md`，复习 231 A1-01～08、231-9 BG-00/02/03/04 和栖月汇黄埔 0 期首链。只读查当前 signed 来源、新库 D01/内容能力与正式发布/运行权威；不修改代码或库、不调用 Provider/商城源、不重放旧 Run，未获当前权威不注册自然 Host。文件仅涉及现有预检脚本、AIP Skill 发布/绑定 Owner、D01 同事务 coordinator 的代码和测试读取。

## 第 4/9–5/9 步：专项与当前实例回读

- `uv run --directory services/aos-api pytest -q tests/extension_runtime/test_ecommerce_analyst_d01_atomic.py tests/extension_runtime/test_ecommerce_analyst_d01_issuer.py tests/aip/test_aip_skill_publication_service.py tests/aip/test_aip_skill_binding_readiness_service.py`：**35 passed**；7 条既有字段/兼容 warning，没有代码改动。
- 当前 signed receipt 通过 `a0v_current_aip_definition_preflight.py`：`aos_current_preview_20260927@a0v_106`、唯一 installation `ccdcb0f0-1040-4bc6-aa0c-d045f5689813`、签名来源 `solution.ecommerce.growth@1.11.0`，定义 6/37/10、Runtime binding 0、writes 0。
- 六实例只读预检：`org-org/dev-project` instances 6、SkillBinding 0、CapabilityBinding 0，唯一 intent 已存在，writes 0。
- 当前 PostgreSQL 只读 SQL：`ecommerce.skill.D01` 为 evaluated、requiredCapability=`material.collect`；`D04` evaluated、所需能力空；`C03` evaluated、`copy.generate`；`C04` evaluated、`script.compose`。同租户 Skill published=0、ReleaseGateDecision=0、PublicationEvent=0、LogicPublication=0、ModelRouteRevision=0、RuntimePolicyRevision=0、BudgetRevision=0、ProviderInstanceRevision=0、AgentRun=0。十个 CapabilityRevision 存在，不代表已绑定或健康。
- 本轮未改前后端，浏览器新交互验收不适用；当前安全 API 8080 的 signed 来源前置仍可读。无新运行实例/业务 Receipt。

## 第 6/9–9/9 步：复审、证据、提交和下一波

与代码一致：普通 SkillRegistry 不能直接发布 evaluated 技能；正式发布需要同租户 exact Eval/PublicationEvent、已发布 Logic 和有效模型路由/策略；CapabilityBinding/SkillBinding/实例 active/预算/健康是后续独立门。当前新库零权威，**A0-V 当前准入和 A1 自然 D01 均未完成**。不能把 35 项测试或六实例当可执行证据。原 W5cam/W5can 的同事务 D01 coordinator 仍未注册 Host；当前无新鲜 TaskRun/MethodRevision，不能重放旧 12 Run 来填空。

下一波编码切片：在现有 `services/aos-api/aos_api/ecommerce_analyst_d01_atomic.py` 与来源 reader 周围设计并实现**只读、确定性、同事务的生产 D01 packet selector**，先用 `services/aos-api/tests/extension_runtime/test_ecommerce_analyst_d01_atomic.py` 写 RED，拒绝零/多/跨租户/过期/撤权来源，只有原 Receipt、当前批准 Plan/TaskRun 与完整 Method/Eval/Metric/Query/EvidenceBundle exact 闭包唯一时才交给原 Owner。生产 Host 保持不注册，直到正式预算/安装/能力/模型权威及隔离 PG 全链通过。另并行串行推进首链最小 Skill `D01` 与内容 `C03` 的合法发布/配置入口；不要求首链前把 37 个全量发布。旧 12 Run 退休与非首链快照逐行证明仍后置。

m1 单写不 push；`dev-org/dev-project` 仅零 canary，230 L0 挂起；已有工作树三项用户文件不纳入本提交。

记忆健康：`scripts/memory/memory-status` 返回 `GREEN_WITH_WARNINGS`，`memory-validate` 返回 GREEN；但投影的 `project_revision=AOS-000802` 和交付状态仍是较早的 P2g 负向门，不能作为当前 `966659e3` 或本波的实时 authority。Prime Agent 进程存在；本波的当前事实先落 AOS 上下文 227/228 与 D-waves，后续需通过正式事件/投影流程更新 Prime，不直接改它的 harness 或把旧投影称同步完成。
