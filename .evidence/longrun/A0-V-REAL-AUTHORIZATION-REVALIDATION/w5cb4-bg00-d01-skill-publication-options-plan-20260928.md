# W5CB4 BG-00 E01：D01 技能发布精确候选选择施工方案（2026-09-28）

## 上位与当前问题

依据 231/231-9 BG-00/BG-03 与栖月汇数字同事产品方案，首链应由真实可配置、可禁入的产品入口完成合法 Skill/Logic/模型绑定，不能让开发者手抄 ID/hash。当前 `SkillPublishPage.tsx` 把发布事件、release gate、模型路由、运行策略、Logic 的十个精确字段交给用户手填；服务端 `AipSkillPublicationService.publish_evaluated_revision` 已有正式 Eval/发布事件/Logic/Route/Policy 权威检查。当前租户 D01 技能仅 evaluated，路由/策略/发布事件等最近证据为 0；不能制造默认候选或自动发布。

## 目标、文件和顺序

目标只做**只读同租户候选**与 UI 显式选择，POST 仍交现有 Owner 现时复核；候选为 0 时清晰指向下一真实配置入口，不提交空引用、不生成模拟 Route/Eval。与 C2b 恢复/当前库 a0v_107 迁移相互独立。

为避免后端/前端同时施工造成半成品误导，分 **E01a 后端只读候选合同** 与 **E01b 前端显式选择** 两个独立提交；E01a 不能称已解决手填 UX，E01b 必须复用 E01a 响应并保留最终 POST 现时校验。

1. 复习 `aip_skill_publication_service.py`、`aip_release_publication_service.py`、`aip_model_runtime_store.py` 和现有路由/权限；明确候选必须保留 exact ID/revision/hash、tenant、生命周期、checker/撤销状态。不得用 `ORDER BY latest LIMIT 1` 自动猜授权。
2. 后端 `services/aos-api/aos_api/aip_skill_publication_options.py` 新增 read-only 枚举；`services/aos-api/aos_api/routers/phase3_aip_skills.py` 增单技能候选 GET。缺依赖以分层 blocker 返回；跨租户、缺 scope、重复/冲突、过期/撤销 fail closed。专项 `services/aos-api/tests/aip/test_aip_skill_publication_options.py` 先 RED，再最小实现，必要时隔离 PG。
3. 前端 `apps/web/src/pages/s2/SkillPublishPage.tsx` 由十字段自由输入改为精确候选选取与复核，选中后仍要显式点击发布；加载错误、0 候选、切换技能与未知 POST 结果不重发。`apps/web/src/pages/s2/SkillPublishPage.test.tsx` 先 RED，复用现有 SDK/Parser，不直接拼未经校验的 JSON。
4. 专项、后端累计、Web typecheck/build、浏览器用当前 0 候选验收禁入；方案/代码安全复审、verification、m1 提交、上下文/Prime 状态核对，进入 E02 最小正式来源/绑定或 C2b 联合正向。

## 停止与风险

不能从一个 release gate 或前端列表推断可发布；只有现有 Owner 的 POST 正式检查与 Receipt 才能发布。当前库 a0v_106 不为此迁移、不读取商城源、不创建路由/预算或外部 Provider。候选查询若发现必须跨多 Owner 拼成不可信“ready”，拆为各层精确候选与 blocker，保持显式人工选择；不以 UI 绿点放开 Runtime。原有用户工作树改动不纳本波。
