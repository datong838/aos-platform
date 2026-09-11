# 经营参谋正式 Eval 目标绑定验证

2026-09-11，基线 `m1@2eb007a8`。

阶段评审宿主现在从已经完成租户、TaskRun、成功 AgentRun Attempt、原始 Artifact 与阶段
Skill 校验的 AgentRun Owner 记录中，构造 exact `AssetRevisionRef`。其固定类型为
`skill_template`，ID、revision、contentHash 来自实际生成请求；正式 Eval report.target
必须完全相等，调用方无法选择替代目标。

新增正向与 target kind/id/revision/hash 四类负向断言。阶段评审、Eval report、真实隔离
PG 结构 Eval、文字输入与文字阶段 subject 联合回归共 `56 passed`，12.26 秒。没有调用
Provider、没有创建发布或修改真实租户。

本切片补上“生成该正文的 exact Skill 就是被评估目标”的关系。Suite case 输入与成功
Attempt 原始 query 的持久派生绑定仍是下一切片，不能由本结果推断已经完成。
