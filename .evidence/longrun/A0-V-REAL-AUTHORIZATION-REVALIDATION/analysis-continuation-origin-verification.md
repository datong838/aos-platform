# SC4-5c3a 当前初始化来源核验

2026-09-14；基线811e53a5；m1，不push。

AnalysisContinuationOrigin在精确完成事件当前来源上下文中核验唯一started决定、精确ActionProposal/Preview及原草稿hash、严格BootstrapIntent与实际CompilationReceipt、当前maker身份/marking、未撤销的初始化权威Evidence正文/hash/actor/时间/原证明。原人工初始化的真实审批事件也回读。回调前后比较，失败保存点回滚。本读取器不授予运行或Provider许可。

真实隔离PG验证来源派生初始化和实际独立审批初始化两条来源；动作拒绝、membership撤销、草稿漂移、Evidence撤销、回调期间拒绝均阻断。证据表不支持FOR SHARE所需UPDATE权限，改为原serializable事务内只读及前后复验，没有授予UPDATE。

累计27 passed/7既有警告/34.56s，AR2 1907/186/93五数组空，diff check通过。来源/能力fixture边界保留，独立审批是隔离测试身份；主租户未部署，没有实际模型或经营执行。

下一SC4-5c3b专用当前数据恢复组合：原来源/初始化证明与真实补齐检查共同成立时，才经内部专用Task恢复门；通用入口仍拒绝。要保持同一原事务、双Run状态一致、重放与失败回滚；之后自动安装政策/真实数据满足/D01-D03 Worker及主首链、八场景验收。
