# 原评审合同兼容与退回锁权限复审

沿231、本Task第九段及42501修订执行。原Store在独立复制库通过固定Contract LOGIN创建两条普通media评审Issue并解决其中一条；hash漂移、幂等漂移、CAS、canary、关闭后再解决拒绝真实执行。解决引用实际非空实验Artifact exact ref。旧Rule明确testOnly，原历史EvalReport没有本轮新评测来源；不是ecommerce_content主体/阶段/Eval gate完整验收，也不是实际媒体成果评测通过。

首次在原return的FOR UPDATE OF run,task处42501（aip_task_run缺UPDATE），保留原intent/script/failure和七个已完成检查，不将其当业务退回拒绝。独立只读读取第一次因SQL字面百分号与占位参数混用产生ProgrammingError，无写；改为参数化LIKE后，准确核对三个Receipt、两个Issue及fixedrole清理完成。create/resolve已提交，未重放。

PostgreSQL16 SELECT FOR UPDATE要求每个被锁表至少一列UPDATE，官方依据：https://www.postgresql.org/docs/16/sql-select.html 。finish只在实验复制库给Run/Task的updated_at列权限，status/version无权，真实状态写42501；补权后原return到RETURN_TARGET_NOT_RUNNING，Issue/Receipt/Run不变。列权限仍允许时间戳写入，绝不称“仅有锁权限”；正式迁移需要评估更严格锁入口或作用域限制，不将本实验授权直接上线。

随后原Receipt故障验证整事务回滚，Issue/event/Receipt计数不变。累计11项检查，其中旧完成七项来自原terminal failure，续接新增四项/四连接。角色/双租户policy/列权限finally清理。独立读取三Receipt exact ref、opened/resolved序列及非空resolution，待退回Issue open1、实验Run queued无Step/ReturnDecision。原报告完整行与未改原clone相同，原clone与当前恢复卷647表/六类元数据一致；无当前库/API/Web/Host/worker/Provider或旧Run改动。

结果绑定两个原脚本hash、syntax与公开证据检查。实验Receipt操作覆盖20/30，尚有十个操作未正向；其中return/content/eval对应主链仍须合法前置和原完整事务兼容。完整Source Task保持ACTIVE；正式登录/独立publisher、预算/八配置、八页恢复和自然首链均未完成。下一项继续已登记的完整Content/source依赖与剩余合同，不能为覆盖率伪造运行状态、报告或安装权威。
