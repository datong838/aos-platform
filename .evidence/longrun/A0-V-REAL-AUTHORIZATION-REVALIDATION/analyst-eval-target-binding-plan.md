# 经营参谋正式 Eval 目标绑定方案

日期：2026-09-11
基线：`m1@2eb007a8`

## 问题与目标

阶段评审入口已经重新核验原始文本 Artifact、成功 AgentRun Attempt、阶段 Skill、当前
EvalContract、passed report 与 release gate，但只校验 report 的 Suite 与合同一致；尚未
要求 report.target 等于生成该产物的 exact D01/D02/D03 Skill。这会留下“正确正文由另一
目标的 Suite 评分”后仍进入人工评审的替换口。

本切片在同一宿主事务内，将报告目标严格绑定为 AgentRun 请求上的 exact SkillTemplate。
目标由宿主已读取的 AgentRun Owner 记录派生，调用方不能另传。

## preHash 与文件

| 文件 | preHash |
|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_command.py` | `a1fb256df668f69ae3db3d43fc71df816660cd399476e183e62506e975ddfd4d` |
| `services/aos-api/tests/test_ecommerce_analyst_stage_review_command.py` | `167f839d158a174b8e65ba3bca62743d6cc57297b54be27f2ddf226172a75b92` |
| `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md` | `5625465de7565565fcb2d5cc450fbbf5854cd12a05fa7933f4838f47c1a279d0` |

## 最小改动

1. 从当前 AgentRun 的 `request.skill` 构造 `AssetRevisionRef(skill_template,id,revision,hash)`。
2. 要求正式 report.target 与该 exact ref 完全相等；类型、id、revision、hash 任一漂移均拒绝。
3. 保持现有 Suite、合同、release gate、Artifact、Attempt、时间与租户校验不变。
4. 不创建 Eval、不发布 Skill、不新增路由、不触发 Provider。

## 退出条件

- 正常 exact target 通过；kind/id/revision/hash 四类漂移失败。
- 阶段评审相邻回归通过，闭包扫描错误集为空。
- 证据落盘并单独提交到 `m1`，不 push。
