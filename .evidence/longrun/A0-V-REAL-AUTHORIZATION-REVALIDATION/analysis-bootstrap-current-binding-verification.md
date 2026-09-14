# SC4-3c3c 当前初始化对象绑定

2026-09-14，基线9aeccbc3。AnalysisBootstrapCurrentBinding已加入原授权模块：原analysis._phase内读取当前Case/Run/CompilationReceipt/Task/Plan/Preview/Evidence；核对原Occurrence、控制回执、安装代次、Case和原幂等目标。仅接受当前草稿Plan与无TaskRun状态。回调后重读并核对，父来源当前权威由原Owner复验。

测试7项含正常actual存储读取、控制回执替换、Plan变化、证据撤销、父审批身份撤销、Case/幂等目标错接。后两项有明确请求快照注入，其余沿实际隔离存储。首次5项import红测；证据测试直接UPDATE被DB拒绝，改走实际撤销事件，未调整产品表权限。

累计33 passed、7既有警告、10.90秒，日志/tmp/a0v-bootstrap-binding-final2.log。AR2 1902/180/93错误为空；memory GREEN AOS-000573。当前读取器不写审批、不授予运行权，独立身份读取尚待ActionStore专用连接。主租户未执行，本项不代表首链成功。

下一波：专用Action准备/审批连接，在原Owner事务中用当前身份和当前对象守卫；继续保留通用入口拒绝与R1未授权边界，然后原子暂停组合和正式事件START。
