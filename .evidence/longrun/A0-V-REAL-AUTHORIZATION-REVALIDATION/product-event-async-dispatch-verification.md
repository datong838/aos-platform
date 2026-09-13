# 异步目标分发验证

基线f808a7df。新增入口强制显式store与精确ClaimTarget；旧同步入口不变。领取前/等待后分别取时间；异常标needs_attention，取消传播，保存回执失败传播，无内部重发。

Red：入口未实现ImportError。Green：异步6项与原领取/PG邻接共35项通过。异步测试使用编排替身，原数据库测试使用专用18432临时schema，不能视为真实installed分析Run验证。AR2-7 1883/168/93，错误数组均空；diff --check通过。

方案一致性：不新增授权、连接fallback或重试策略；超时取消仍需后续Receipt对账。主库和运行Host未改，未push。

下一波：正式分析承接前核对当前claim与事件policy/Case关联；现有AnalysisAdvanceHostService.revalidate核对内容exact引用，但尚未显式验证claim所有者/有效期。接线必须补齐这一入口，不能把领取投影当权限。
