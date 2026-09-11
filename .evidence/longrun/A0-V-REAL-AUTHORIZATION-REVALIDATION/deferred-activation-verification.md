# 开发未核价激活与当前授权禁入

2026-09-11，基线98b0b4e3，Task A0V-DEFERRED-ACTIVATION-20260911。用户开发费用延后授权持续有效，不索取单价。

最初合同测试1失败8通过，证实合法deferred active被阶段性限制。移除此限制，允许active/suspended/revoked完整表达；金额字段仍必须None，scope/模型/审批/时区窗口/CNY约束保持，商业无授权全空价格仍拒绝，旧字段序列化保持。

复核又发现旧exact active引用在当前head已撤销后仍可能通过：Owner专项1失败12通过；预算/Invoker专项2失败1通过。新增共享require_current_development_price，Model Owner及实际Invoker在Secret/transport前检查当前head与被引用版本/hash/active及scope；deferred BudgetPolicy在require_exact_active检查当前head。仅开发opt-in生效，旧商业版本pin行为保持。此为调用前快照核验，不声称消除了核验与网络发送间所有并发撤销窗口；宿主锁/epoch/审批仍独立约束。

最终合同/开发绑定/Owner/Invoker61通过；Resolver/治理合同/开发授权57通过，明确排除默认数据库的无route集成1项；新增真实PG Price Owner专项1通过。合计119通过、1未选，不称全库回归绿色。既有Pydantic/Starlette警告及JDBC退出logger问题仍在。

PG专项独立随机schema，生产三表LIKE INCLUDING ALL，显式FORCE RLS及aos_runtime连接；active/suspended/revoked三个正式Owner修订各自保存，幂等重放仍3张receipt；旧历史回读保持但当前使用拒绝，canary读取0。完成只清理该schema。没有在真实org-org配置中发布Price/Model/Route，无Provider调用；API仍运行1100b936尚未加载本波代码。

下一波用既有三个真实文本样本及其不可变attempt记录形成正式Eval对象、模型与单文本路由，绑定本次开发授权；继续职责/技能/安装就绪与经营参谋首次分析，不把文本Gate扩张为视频/语音或完整业务质量。首链、八场景与连续观察尚未完成，不push，230 L0挂起。
