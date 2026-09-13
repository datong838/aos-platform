# 正式分析承接服务源码验证

基线5aa0b277。ProductEventAnalysisService复用消费服务当前来源/控制上下文，exact原事件回读、锁claim、当前growth安装、analysis dispatch；释放事务后installed命令计算，二次全快照重验，通过sealed registry runtime_port在外层事务创建/回读分析Receipt，末尾重验claim后唯一commit。

Red缺失服务4失败。PG首次复用旧fixture窗口过期，领取正确返回None；新测试独立body使用当前时间重新构造并hash原始测试方案，未更改生产时间门。第二轮发现profileRef带receiptId:null，不符合已有Host严格协议；组装命令时剔除空字段，保持exact语义。

Green29项。编排替身验证无事务跨await、漂移/timeout/write失败不commit、sealedHost调用后重验claim。真实18432隔离PG验证当前claim/control/政策/Case精确准备和撤回审批拒绝；Source/installed/group-lock仍具名替身，尚未证明真实Host创建Run。AR2-7 1886/169/93无错误；diff --check通过。

主库/Host未改，未push。下一波factory及已领取事件原批次定位；不得让任意扫描run承接其他事件。随后worker接线与真实Host写入集成验证。总目标仍未完成。
