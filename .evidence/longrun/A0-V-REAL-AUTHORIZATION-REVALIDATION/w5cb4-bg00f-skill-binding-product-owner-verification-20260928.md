# W5CB4 BG-00f｜SkillBinding 产品 Owner 入口验证与重启接续

## 本刀范围

按 `w5cb4-bg00f-skill-binding-product-owner-plan-20260928.md`，复用现有 `aip_bindings.py` Owner。新增精确只读候选、正式 published Skill 与 exact RuntimePolicy 读取、人工确认后一次不排队创建、同租户 Binding/Receipt 回读、未知结果原命令标记与禁止重发。目录页仅对已安装且未绑定的技能显示入口；当前 D01@1 为 evaluated，只提示正式发布后配置。没有对当前数据库发 POST，也未启 Host/worker/Provider。

## RED / GREEN 与合同复核

- RED：新增 candidate、product、panel 测试在模块尚不存在时均以 missing import 失败；随后最小实现。
- `PATH=/Users/ddt/.nvm/versions/node/v20.20.2/bin:$PATH pnpm --dir apps/web exec vitest run src/pages/s2/CanonicalAgentRegistryPage.test.tsx src/pages/s2/SkillBindingCreatePanel.test.tsx src/api/aipAgentControl/skillBindingCandidate.test.ts src/api/aipAgentControl/skillBindingProduct.test.ts`：17 passed，退出码 0。测试覆盖 evaluated 禁入、跨租户与漂移、预算缺失、CapabilityBinding 歧义/过期/降级、单次提交后 Receipt 与 GET 回读、未知结果不重发。
- 同 PATH 下 `pnpm --dir apps/web exec tsc --noEmit`：退出码 0；`git diff --check`：退出码 0。
- 复核 `routers/aip_bindings.py` create/get、`aip_skill_registry.py:create_binding`、`aip_agent_registry_contracts.py` CreateSkillBindingRequest/Receipt 与 `routers/aip_model_runtime.py` exact policy GET。产品请求字段与 Owner 合同一致；Owner 在 POST 时重验 published/tenant/instance/能力和幂等。
- HTTP 只读检查：Web `http://127.0.0.1:8434/aip/agent-catalog` 200。`/health` 返回 404，仅说明该路径不是健康端点，不能据此判断 API 故障；重启后需重新核对真实健康路由和当前库身份。

## 停止门与下波

- 当前 D01 未正式发布，当前正式 Dataset/Case/Judge/运行策略/能力绑定/预算来源仍缺；本刀只证明代码在隔离测试中工作，不是当前业务首链通过。浏览器 pilot 本会话不可用，未编造截图。
- 重启电脑后，先复核 m1 HEAD、工作树其他人改动、当前权威卷 `aos-a0v-recovery-pg-data`、库 `aos_current_preview_20260927@a0v_111`、独立备份和 PG/API/Web 健康。Host/worker 保持关闭。随后继续 BG-00g：现有 Owner evaluate/activate 的显式预览、CAS/Receipt 与未知结果只读对账；D01 正式 Eval 来源仍并行独立推进。
