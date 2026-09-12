# 选列快照读取验证

2026-09-12，基线7054e061。新增 pipeline_selected_snapshot.py 和对应测试，现有调用入口保持原行为。

先锁当前租户源行、读取同事务配置并比较 exact ref，再由私有 JDBC 连接执行唯一一次带 columns/where_equals/limit 的只读读取。数量达到 limit、缺/多字段、重复/空主键、已选范围列不符、超过接纳时限/有效期均拒绝整个结果，不返回部分批次。异常仅固定 SELECTED_SNAPSHOT_READ_FAILED，无连接秘密或源行；不重试，不写业务对象。

RED缺少模块收集失败；实现后新增12项与选列21项通过，关联私有连接清理、JDBC运行时、原有源适配、版本绑定合计 **93 passed**，4.03秒，7个既有警告。AR2 ar2-7为1795/158/93，五类错误数组为空；git diff --check通过。

测试使用命名假连接和假源，不是实时数据读取/完整性证据。返回数严格小于limit只证明本次查询未达到截断阈值，不证明多表一致性或真实表引擎/Schema。空结果后续只能走既有empty observation流程，不能据此删除已有对象。更短请求时限只控制结果接纳，驱动仍为30秒socket timeout，不声称硬中断。

尚未接正式运行控制、尚未启用P01或读取商城数据。下一波持久PipelineRuntimeControl及最新SourceSelection绑定检查；正式执行仍必须当前检查并统一进入ScheduleRun/Ingress恢复链，禁止新增旁路。未push，230 L0挂起。
