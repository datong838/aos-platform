# 经营参谋正式 Eval case 同源绑定方案

日期：2026-09-11

基线：`2131f1b0`

状态：实施前冻结

## 目标

阶段人工评审只接受由当前成功 AgentRun 的原始 query 派生、并已冻结进当前 Eval Suite 的
唯一结构 case。query、output、Attempt、Suite、Skill target 与 Eval report 必须形成同一条
精确来源链，任何调用方自报 case 或仅自洽 hash 都不能形成评审权限。

## 方案

1. `AnalystStageReviewCommandService` 构造时必须显式注入已安装 growth 包的
   `structure_case_from_query`；宿主模块不反向 import 包。
2. 同一阶段事务内验证 output Artifact source 的 attemptId、agentRunId、requestHash，并
   查询该 Attempt 唯一的 `agent_query_input` Artifact。
3. 经 `read_agent_query` 用当前 markings、Attempt ID、requestHash 回读正文，再调用包函数按
   stage 派生严格 case；包函数异常统一阻断。
4. 读取 EvalContract 指向的 exact Suite，要求 Suite hash 与合同一致、target 等于 AgentRun
   request 的 exact SkillTemplate，且只包含一条 required positive case。
5. 该 case 的 input Artifact 必须是 revision 1，contentHash 等于派生 case 的 canonical hash；
   expected Artifact 必须存在。报告仍按已有 Reader 验证原始 output、StageAttempt、合同和门。

## 边界

- 本波不创建或修改 Suite、EvalContract、Eval run、报告与 release gate。
- 本波只增强 accept/return/reject 前的只读核验；revoke 继续不重读已失效产物。
- 未注入包函数、query Artifact 缺失/重复、正文无权访问、Suite 多 case 或 target 漂移均 fail closed。
- 既有尚未包含 query Artifact 的历史成功 Attempt 不能补造通过证据，应由新 Attempt 重跑。

## 文件与 preHash

| 文件 | preHash | 修改 |
|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_command.py` | `ca5b442e0886b5bf31a6b6da0f2d89628a000470cbae274e08afb95167e4b999` | query Owner 回读、包派生、exact Suite case/target 绑定 |
| `services/aos-api/tests/test_ecommerce_analyst_stage_review_command.py` | `e66faa6dfb516f02c2dbfeccc379dcca914d9820cecda61d8add96a183693c9e` | 正向绑定与 query/source/Suite/注入负例 |
| `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md` | `755a9921e593878a5bbc790b43022cb8f68ef315099d5eb35e217e7f66143a81` | 登记 9.7 增量切片 |

## 退出条件

定向与联合测试、Python 编译、`git diff --check`、AR2-7 closure 全绿；落验证证据并只提交
清单内文件。通过仅证明评审证据同源，不代表真实首链或八工作台已经完成。
