# SC4-5c3b 专用当前数据恢复事务

2026-09-14；基线17dec955；m1，不push。

新增内部_AnalysisDataResumeSession及专用sealed registry工厂，固定精确Origin、原数据库事务、目标Receipt与严格resume_data命令。AipTaskStore普通初始化恢复仍阻断，仅精确且正在自身来源事务中执行的Session可进入；逐次核验原Task/版本、固定Host actor/reason、readonly Profile及原_resume_authorities完整数据检查。退出try/finally清除内部执行态；调用者bool不能代替Session。

为数据检查时保留WAITING_DATA，仅专用Session路径Task→domain，外层来源保存点失败回滚；普通恢复维持原domain→Task顺序，未改变既有语义。

验证：55 passed/7既有警告/42.48s，包含实际sealed Host缺Fulfillment拒绝；明确data-readiness与dispatch fixture下，实际两个状态Owner共同推进、domain失败后Task回滚、错误actor拒绝、Session外直接使用拒绝，以及原数据恢复/分析Host/启动回归。正向状态组合不是完整Fulfillment或sealed统一Receipt验收；完整真实补齐仍待后续。最初测试collection参数冲突已纠正，未将其称作业务红测。

AR2 1908/187/93五数组空；memory GREEN 1101/1084/2701；diff check通过。全部临时隔离PG，来源/能力仍fixture，无主安装部署/模型调用/经营步骤。该Session不授予Provider、预算或经营方案批准。

下一：先核对主租户可用的真实数据物化、数据需求消费入口和既有补齐Owner，补全自动数据政策/队列消费/完整补齐→统一恢复Receipt的实际链；再接已有D01/D02/D03 Worker、新安装候选、主首链及八场景观察。主首链未完成，不以本次状态测试计完成率。
