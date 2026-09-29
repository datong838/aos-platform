# W5CB4 BG-00g｜SkillBinding 原 Owner 评估与激活产品入口验证

## 方案与改动

基线 `m1@6a3bff81` 的 RED：`skillBindingLifecycle.test.ts` 因缺实现模块退出 1。复习 `231`、AIP-6 BIND-3、`aip_bindings.py` 与 `AipSkillRegistry` 后，按已提交 `w5cb4-bg00g-skill-binding-evaluation-activation-plan-20260928.md` 新增 `apps/web/src/api/aipAgentControl/skillBindingLifecycle.ts`（四 exact 依赖候选）及 `skillBindingLifecycleProduct.ts`（published Skill/策略、Owner preview/evaluate/activate、CAS/Receipt/Binding 回读）；新增 `SkillBindingLifecyclePanel.tsx` 并接入 `CanonicalAgentRegistryPage.tsx` 的已有绑定行。跨租户、错 hash、预算漂移、未 active 实例、歧义绑定、过期快照均禁入。当前 D01@1 evaluated 时页面不发预览/评估/激活请求。

命令通过 `apiPostUnqueued` 发往现有 Owner，预览没有持久业务写；评估与激活在只读前置回读完成后、POST 前保存原幂等键/绑定/版本/快照未决标记。POST 或回读结果未知时只允许读绑定状态，未取得原 Receipt 不清标记、不换键重发。Binding 激活与 Host/Run 仍为独立门。未新增平行 API、未改后端 Owner 或数据库迁移。

## 新鲜验证

- 前端 RED：`skillBindingLifecycleProduct.test.ts`、`SkillBindingLifecyclePanel.test.tsx` 缺模块均退出 1；GREEN：`PATH=/Users/ddt/.nvm/versions/node/v20.20.2/bin:$PATH pnpm --dir apps/web exec vitest run` 七个 SkillBinding/目录相邻测试文件，`38 passed`、退出 0；覆盖四引用、租户/hash/CAS/预算、Owner 预览阻断、正向评估/激活、Receipt 与 GET、未知结果、防重、发送前失败不误标未知、歧义绑定禁入。
- `PATH=... pnpm --dir apps/web exec tsc --noEmit` 退出 0；精确 staged diff check 待提交时复核。
- 后端相邻 `services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/aip/test_aip_binding_api.py -q`：测试专用 `5433` 初次未启动而 setup 5 errors，启动 `colima-aos-a0v-test-only/aos-a0v-test-pg` 后 `5 passed`、退出 0；`test_aip_skill_binding_readiness_service.py -q` 为 `3 passed`、退出 0。测试使用可销毁 test-only 库，不以 fixture 当真实实例。
- 当前权威容器 `aos-a0v-recovery-pg` 的 `BEGIN READ ONLY` 回查：`aos_current_preview_20260927@a0v_111`，`org-org/dev-project` SkillBinding 0、CapabilityBinding 0、全库 Runtime Binding 0；`ROLLBACK`、退出 0。8080 `/v1/health` 与 8434 `/aip/agent-catalog` 200。未调用当前 Binding POST、Host/worker/Provider、商城源、旧 12 Run 或手工 run_definition。
- 今日 09:04 全栈重启独立证据见 `w5cb4-daily-latest-stack-20260929-0904.md`。`browser-pilot` 工具在本会话不可用，无新截图和交互验收；Vite 路由 200 不算页面业务通过。

## 方案一致性与余险

SDK 只允许原 Owner 的 route/policy/gate/budget 四依赖；Owner 自身在事务中重算新鲜依赖并做版本 CAS。页面不从自由文本、旧 Logic Eval 或测试 fixture 生成正式来源。未知结果标记存在本机浏览器存储，换设备或清理站点数据不能作为完成证明；服务端 CAS/Receipt 仍是最终防重权威。当前无 published D01、正式 Dataset/Case/Judge/Report/Gate、绑定和预算/能力配置，故只是可供未来正式来源使用的产品入口，不是首条经营闭环。

## 下波

BG-00h 直接推进 D01 canonical Eval Dataset/Case/Judge 与执行器的正式产品来源和真实数据安全入口。先核对上位 AIP-4 方案、现有 Registry/Runner、脱敏 Receipt/租户边界与当前空库；文件级计划与 RED 后最小实现。不得拿旧 `/aip/evals` Logic 结果或合成样本发布 D01。正式来源齐备之前保持当前实例禁入、Host/worker off。
