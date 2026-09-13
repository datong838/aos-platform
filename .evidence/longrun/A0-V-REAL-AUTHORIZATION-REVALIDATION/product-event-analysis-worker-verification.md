# 生命周期分析分发接线验证

基线7873e6d6。Worker每target每tick最多1条event analysis claim，总≤4；空发现页仍处理持久任务。进程唯一owner，显式scoped runtime Store，origin当前定位/markings/factory/AnalysisService，取消传播，未知结果不重发。analysesAccepted仅Receipt接收计数，不等于分析完成。

真实PG Red发现异步默认datetime含微秒，被原Store UTC整秒协议拒绝。修正默认clock，等待后仍重新取时间。ClaimTarget增加可选trigger_source，worker固定event，原接口不变。

Green39项worker/原PG/async回归。真实18432证明默认clock领取并记录Receipt且不重复调用，错误trigger类型不领取；编排替身证明空页持久任务、exact事件目标/original run传递、取消和生命周期清理。真实业务Run尚未执行，不能将fixture Receipt当正式Run。AR2-7 1887/169/93无错误；diff --check通过。

未主库迁移/Host重启/push。下一波：现有AnalysisAdvanceHostService真实数据库创建/Compilation/TaskRun/Receipt集成；修复实际阻塞，再准备新候选和安装验收。独立发布账号门仍未解决。
