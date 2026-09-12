# 同范围续期的原输入恢复验证

2026-09-13，bf273acc，主A0-V Lease，m1单写者。

PipelineSourceClaimOwner.read_saved_current 要求当前exact控制且已有原输入；同control家族较新revision只允许有效时间和selection ref变化，原范围/限额/配置/代际/actor均不变。原Control decode/hash与原claim核对。原记录不改、不新增调用，不提供源读取授权。常规reserve/read_current继续拒绝新ref重读旧run。

ControlledIngressJournal增加明确saved_recovery内部标记；ControlledSnapshotExecutor.resume_saved只读已保存parent，再复用原恢复/投影/Dataset链，永不调用prepare/reserve/source。仍要求running Schedule；failed状态需既有claim_failed_run原子恢复，后续正式入口需要接入该步骤。

RED：6项缺read_saved_current；实现后与原claim Owner合计25 passed。再新增真实PG续期集成2项缺resume_saved；装配后含正常/失败恢复/续期/未知源拒绝的14项通过。原journal、source preparation、projection回归30 passed。测试分组存在部分重叠，不能将所有数字当唯一测试总数。清册1804/158/93五类错误数组空，diff check通过。

真实PG模拟批准已过期后追加同范围有效期，原对象已投影、Dataset失败任务恢复成功；调用总数始终1，claim/base Receipt/object/Dataset Receipt不增加；完成后重放为completed_replay。没有原输入的未知源结果，即使续期仍PARENT_REQUIRED。row_limit/max_source_calls扩展、actor改变、当前否决均拒绝。

签名资产与源输入仍fixture，主库未新增批准/读取商城。下一波正式调度绑定、受控执行服务和主API重载，随后真实P01首链。跨配置或跨包范围转换旧输入不在本次恢复协议内。
