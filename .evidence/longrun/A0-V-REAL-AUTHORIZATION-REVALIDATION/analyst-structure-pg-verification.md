# 实际隔离结构评估报告验证

2026-09-11，基线f0036d57。6项实际PostgreSQL验证全部通过，4.17秒：portrait/diagnosis/solution-design各合法与非法原文一组。正式Task/Plan/Run/Step和文本Artifact存储、权限读取、EvalRegistry/Run/Report均实际执行。报告exact subject/stage和hash回读一致，无正文/伪造批准标记；相同键重试被既有Runner拒绝，target只执行一次，报告只有一份。

非法回答的EvalRun状态仍succeeded（评测执行成功），但报告gate_passed=false（回答未通过）。没有把执行成功误报为回答通过。每组只建单阶段隔离任务，不证明三阶段连续链；发布合同resolver、来源库存、target/judge注册引用仍fixture，目标函数实际执行。本波只新增测试，不装配生产入口。6个随机副本均退出正常清理，主库不修改，模板历史记录保留。

下一波：从实际生成请求和Owner核验输入形成评估来源规则，避免手填来源计数；再生产受控target/人工评审接续与完整联合图。真实源SSH接入问题仍待恢复，真实首链未完成。
