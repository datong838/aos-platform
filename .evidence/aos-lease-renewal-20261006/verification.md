# 续租工具验收

RED：新增10场景因接口缺失失败，原18测试通过。
GREEN：28 memoryctl测试通过；联合恢复门回归72测试通过。git diff --check通过。

方案一致性：原scope/base_revision/created_at/outputs不变，只延长expiry；当前authority CAS、完整原记录比较、Owner、唯一Lease、Delivery、范围冲突均拒绝优先。原恢复门和wake观察器无需放宽严格一致性条件。历史先落盘，失败不自动重试。

限制与风险：调用者的归属复核说明不能替代外部身份授权；多文件写入不提供事务性，部分失败必须只读对账；未提供自动修复或CLI入口。工具测试通过不等于原Task续租，更不等于恢复门和自然首链通过。

本轮仅登记并完成机制Task，原六业务Lease、当前库、服务和Goal控件不改；下一步独立核验原Owner/线程/终止进程/精确HEAD与文件后再显式续租。
