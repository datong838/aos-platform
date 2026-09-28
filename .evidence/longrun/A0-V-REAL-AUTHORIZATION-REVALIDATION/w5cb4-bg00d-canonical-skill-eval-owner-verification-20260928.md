# W5CB4 BG-00d｜canonical 技能评测来源对账与页面纠偏

- 方案：`w5cb4-bg00d-canonical-skill-eval-owner-plan-20260928.md`；仅修改 `apps/web/src/pages/s2/SkillPublishPage.tsx` 与相邻测试。AIP-4 E1A/E1B 定义 canonical Suite/Report，E1C 明定 `/v1/evals/*` 仅兼容；现有 `/aip/evals` 固定 `logic_graph`，不能出 Skill EvalReport。`aip_eval_authority.py` 无生产写路由。
- RED：先加测试要求旧页标注 Logic 兼容、技能阻断处标明正式 EvalSuite/Report/Gate/Event；首次执行 `SkillPublishPage.test.tsx` 为 `1 failed, 3 passed`，失败于旧“评测门控”文字，退出 1。
- 最小实现：导航改“Logic 兼容评测”；删去误导的“去评测确认门绿”按钮，在技能 release blocker 下说明正式四段来源。发布按钮、候选、幂等、Receipt 代码均未变。专项 `SkillPublishPage.test.tsx` 4 passed、TypeScript `tsc --noEmit --project tsconfig.json` 退出 0、`git diff --check` 退出 0。命令行旁指定的第二测试路径未存在，Vitest 实际只运行 1 文件，故累计仅声称 4 passed。
- 本时点只读 SQL `BEGIN READ ONLY; ... aip_eval_suite_revision/aip_eval_run/aip_eval_report_revision WHERE org_id='org-org' AND project_id='dev-project'; ROLLBACK` 退出 0，均为 0。新栈 `/aip/skill-publish` 与 `/v1/health` HTTP 200；browser-pilot 工具不可用，无截图与实际点击证据。此波不写当前库、不发 Gate/Event、不启 Host。
- 方案一致性：只纠正错误的产品入口，不伪造 canonical 评测生产者。风险仍是正式 Dataset/Case/Judge/执行器与 Owner 缺失，Skill 发布与绑定仍禁入。下一波 BG-00e 以一个必要 Skill 的合法来源逐项设计并接线，缺外部证据时只读核验。
