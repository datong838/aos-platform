# 双 parent 逐调用费用前置核对

基线 be2a02fdfd77820c01f46899610cd3fdeabe72c6 / AOS-001603；唯一原线程、原 Task 与有效 Lease，不新建写者或替代 Goal。

已登记候选：① 原子分配合同中的逐调用费用和累计 parent 风险桥，须先确认 deferred 价格与风险 proposal 含义；② 新 Manifest reader 的实际锁等待过期验证，复用完整原始 Judge 隔离测试及合法新审批。新 Source 联合测试另需资源门，不借用过期 Source。

本步选择①的安全前置：只读原保留隔离库 5434 / aos_test_379975a6f96d_ti4_test / cluster7693564235776004128 / a0v_159，从上一轮完整 native manifest 精确引用读取两侧原价格、预算 policy、activation receipt 与原 proposal。读取不用 FOR UPDATE/SHARE，不刷新时间窗口、不生成 hold、不清除义务。

文件仅本 Task 下本计划、cost-risk-reconciliation-1603.py 与 result JSON；不编辑已被其他 Lease 占有的 budget_cost_runtime.py。核对 proposal 自洽及原价格哈希，记录实际 amount 是否 deferred、每申请风险、总风险、最大申请数及累计账本计数。原 parent 已回滚，不把历史 fixture 作为新授权。

完成标准：精确原始引用可回读、正文哈希一致、只读事务独立确认、前后风险计数相等，明确哪些结论仍缺真实 transport/Usage/逐调用 allocation/finalizer。此调查不关闭五个 parent Task、不宣称业务完成。
