# 调度原运行恢复接线验证

2026-09-11，基线a5cdd5ff，A0V-SCHEDULE-RECOVERY-WIRING-20260911。

execute_schedule内部恢复参数要求trigger=recovery且原run/claim齐全，不允许新scheduled_for。原claim事务提交成功后用原runId进入durable executor；重复claim返回duplicate且不启动/不回写。领取增加expected_schedule_id，调度错配在改状态前拒绝。现有manual/cron调用保持，不扩公开HTTP接口。

新增恢复接线测试修改前2失败12通过，最终30组合通过：4隔离PG Journal/claim组合、17调度Mock、9实际durable选路Mock。PG新增错误schedule拒绝且零claim记录；已有并发/禁入回滚通过。Mock证明不调用新run claim、原run参数、重复不执行及缺参数拒绝。diff-check通过。非全PG整链/真实源恢复证明。

边界：当前内部函数可恢复，页面/公开API和自动恢复worker尚未接入；领取后崩溃不会抢占未知running。public未迁移、API未重载，真实首链与八工作台未完成。下一波核验整条恢复路径的真实PG事务与安装迁移兼容性，再接产品恢复入口。不push，230 L0挂起。
