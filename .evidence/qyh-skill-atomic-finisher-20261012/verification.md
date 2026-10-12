# 受限原子终结验收

新内部helper在caller SERIALIZABLE事务/SAVEPOINT内：独立两角色LOGIN/有限Run及event权限核验；writer先锁intent及exact request/version，再全量核Target/Judge派发、输入/结果hash和签名发生/观察时间因果；finisher复用原Run CAS/event；writer复用原全签名/current root/Receipt/Report/sidecar登记，CAS intent version；角色恢复。无commit、retry或外部调用。正常失败评测也由原report汇总决定，不更改gate阈值。

最终专项/相邻85PASS、0skip、7既有warnings（14.53s）：原Run转态、独立身份、旧caller登记、完整intent只读对账与派发回归一并通过。正向独立连接观察事务前状态仍running/无报告，commit后Run/Event/2Receipt/Report/Proof/intent全一致，原签名消费者及全intent消费者COMPLETE。两原生连接竞争同intent只有一commit，冲突不自动重试。晚期CHECK在最终proof写发生，保存点整体rollback；caller捕获后commit也没有虚假成功。错误签名/输入/版本/请求/租户/宽ACL/事务mode/未来事件/错误事件类型/布尔版本拒绝。

初始RED为缺新模块collection error；首原生运行错误引用o.created_at，1fail/11pass不能证明晚期负门；已修正为真实observed_at，并收紧精确晚期CheckViolation。第二轮暴露测试误用RuntimeError接EvalExecutionRejected，8fail/4pass；修复断言而非放宽产品拒绝。随后累计81pass、增加原消费者/并发13pass，最后加强事件时间语义后累计85pass。失败日志保留。

仅新完整UUID实验DB、真实独立签名夹具及测试LOGIN/NOLOGIN finisher有限GRANT/RLS，测试后删除这些本轮临时资源；没有用管理员在helper中切身份，无旧writer Run UPDATE放宽。正式finisher角色/权限迁移与连接配置仍未安装，producer初始Owner/审批/预算/网络/真实Target/Judge仍PENDING；本helper仅终结已准入的新Run，不启动运行、自动publish或释放预算。无真实库写、API/Web重启、旧12Run重放。原Goal/full restoration/自然八台首链不收口。

方案与代码复核一致：原writer和CAS算法未修改；输入事件/作用域/DB时间、原签名权威与角色边界保留。有效权限检查只覆盖本段Run/event能力，不声称完整账户或所有函数权限审计。新code无正式路由/配置入口，部署仍缺精确原权限安装。无页面改动，不需浏览器验收；最新冻结API候选在新代码后必须重新生成。既有22个tracked用户改动保护。
