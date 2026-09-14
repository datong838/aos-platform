# SC4-4b1 共享原Run创建

2026-09-14，基线199d8340。从AnalysisAdvanceHostService._start_lineage提取_prepare_start_run，原Application/RunStore和确定性Runid/幂等键不变。重试读取验证现存初始Run，仅接受原Host创建的r1 PREPARING/RUNNING，复用原createdAt走原幂等请求，防止预创建与最后Host绑定因时间不同冲突。

两项红测缺方法后实现；累计29 passed、1既有xfail、7警告，4.51秒（/tmp/a0v-start-run-green.log）。实际PG重放保持同一Run/时间，无TaskRun；外层故障回滚。原完整START缺编译桥接的严格xfail保留，不以方法提取冒充首链完成。

AR2 1904/182/93错误为空，memory GREEN AOS-000573。下一SC4-4b2在正式事件服务中调用完整准备/派生初始化再原Host绑定，完成后才更新真实START验收。无主租户/包资产变更，无push，230 L0挂起。
