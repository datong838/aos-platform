# W5CB4 BG-00d｜技能发布页与 canonical 评测真源对齐方案

## 事实与边界

- 231 长程计划以真实来源、精确评测、正式放行与 Receipt 判完成。AIP-4 E1A/E1B 的 `aip_eval_suite_revision`、不可变 `aip_eval_report_revision` 是 canonical 评测真源；E1C 明定旧 `/v1/evals/*` 只是 compatibility surface，不能成为生产 Suite/Report 真源。
- 现有 `/aip/evals` 由 `apps/web/src/pages/s2/aip.tsx` 使用旧 `/v1/evals/suites`、`/v1/evals/run`，请求目标固定 `logic_graph`。`aip_eval_authority.py` 只有 canonical 只读接口；`AipEvalPackRegistry` 与 `AipEvalRunner` 有受控服务，但当前无正式 Skill EvalSuite/Report 产品生产入口。当前 `org-org/dev-project` 的 canonical Suite/Run/Report/Gate/PublicationEvent 均 0。不得用旧页面、合成 Case 或模拟结果冒充技能放行。
- `SkillPublishPage.tsx` 却把 `/aip/evals` 标成“评测门控”“去评测确认门绿”，会误导操作者把旧 Logic 兼容报告当 Skill 放行依据。后端发布仍 fail closed，但页面引导不符真源。

## 本波最小文件与顺序

1. `apps/web/src/pages/s2/SkillPublishPage.test.tsx` 先增加 RED：旧评测页必须明确标识仅供 Logic 兼容检查；技能发布阻断处说明 canonical EvalSuite/Report/Gate 与正式事件须由相应 Owner 建立，不能把旧页当技能放行入口。
2. `apps/web/src/pages/s2/SkillPublishPage.tsx` 只修正两处旧页链接文字与阻断说明；不改变发布按钮/命令、候选筛选、幂等及 Receipt 逻辑，不暴露无来源的创建表单。
3. 跑该页专项与邻接测试、TypeScript、diff check；适用时 browser-pilot 截图，当前工具不可用则仅记录 HTTP 与测试边界。再写 verification、D-waves、01/06 与 Prime authority，精确提交。

## 下一波 BG-00e

先做 canonical Skill Eval 生产者的正式来源设计与最小合法接口：精确 evaluated Skill r1、真实 Dataset manifest/脱敏 Receipt、Case artifact、Judge/模型路由与预算来源、Actor/租户权限、可复核执行器及报告权威。缺任一来源时只展示缺口与只读核验；不把当前旧 Logic Evals 复制到 canonical 表，也不在当前库编造 Suite/Report。首链只选必要 Skill。
