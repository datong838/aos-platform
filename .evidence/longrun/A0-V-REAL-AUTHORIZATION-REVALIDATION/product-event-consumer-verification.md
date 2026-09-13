# BG-02 三阶段消费本体验证

基线93ed6def。新增内部消费Service：两次当前SourceOwner事务夹一次installed core计算；当前控制dispatch整组、当前策略/Case、enabled binding revision、该revision原enable receipt、当前批准/方法、原批次metadata、core安装快照全部相同才能写。record_event_batch在Reader回调内执行，批准/绑定/安装/SourceOwner退出检查后才提交。无启用改变、无源ACK或序号水位、无重试或直接Run写入。

RED缺模块；首轮流程+旧控制+Reader16通过。PG补验初轮2项因断言表名误写automation_outbox失败，正确表为automation_occurrence_outbox；修正后总42项通过（7条既有依赖警告）。真实临时PG验证当前enable receipt承接Occurrence/outbox、停用/撤销批准拒绝、写后授权变化回滚；source、core runtime快照及group-lock在该测试中是明确替身。流程测试证实IPC没有持有数据库事务、空批次不调用、快照变化不写、超时单次。不能声称实际签名包已运行。

AR2-7扫描1881/分类168/迁移93，各错误数组空；diff通过。主库未迁移/未重启/未部署/未push。后继平台工厂和受治理worker装配、Occurrence到分析Run仍待完成，真实首链未完成。
