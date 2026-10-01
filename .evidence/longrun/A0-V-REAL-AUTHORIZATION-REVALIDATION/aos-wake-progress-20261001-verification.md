# AOS 唤醒强化 v2 验证

Task AOS-WAKE-PROGRESS-20261001。新增进展复查信号器，不启动工作进程、不操作Goal/数据库。
- RED：python3 -m unittest discover -s scripts/long-task-watchdog -p test_aos_wake_progress.py，缺模块退出1。
- GREEN专项：同命令6 tests OK退出0；覆盖无变化阈值、重复/乱序提醒去重、新代码重置、身份/分支隔离、文档提交不算代码。
- 相邻回归：python3 -m unittest discover -s scripts/long-task-watchdog -p 'test*.py'，70 tests/1.531s/OK；测试日志/tmp/aos-wake-v2-tests.log。
- 原基线现场检测：code_commit=16604c73，code_age_seconds=16585，REVIEW_REQUIRED；重跑同一event返回完全相同state，不增计数。progress.json权限0600。
- app automation_update成功更新既有aos-2，view已回读；TOML断言ACTIVE/15分钟/同线程/v2/检测命令/任务重选/定期告警全部通过。prompt SHA256=698e72c0c42620a81a57625ae7776b7458adb5ade27ce0634eecd5ebdd09f930。
- 复审：无代码提交仅复查信号；实际测试/调查可另举证。检测无代码执行权、Goal状态变更、数据库写和网络。旧watchdog未改绑启动；不产生第二写者。源代码/自动化配置变更不算经营首链完成。
- 待验收：下一次真实heartbeat是否调用检测器并执行有证据的接续/阻塞报告，跨断联/电脑休眠恢复及24h观察尚未完成。机器离线、额度耗尽或宿主无法调度时，本检测器不能自主运行；提示词仍需宿主执行，不能承诺永不停止。
- Goal当前blocked未修改，工具未提供resume；本波不得声称其已恢复。用户可用Goal恢复控件；业务后续仍需区分待裁决签名协议与独立授权工作。

日志SHA256=a97d5810703822b84974ad30eb25e21e3bb6c9c79d64d3647964bbe6e950e042
