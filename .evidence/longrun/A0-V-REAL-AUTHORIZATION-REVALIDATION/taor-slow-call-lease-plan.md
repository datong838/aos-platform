# 慢调用租约维持施工方案

2026-09-11，基线 b4102ec2，Task A0V-TAOR-SLOW-CALL-LEASE-20260911；m1串行、不push、230 L0挂起。

preHash：aip_taor_loop.py=b5c8b96a0a7d077c83b4f21c363057ffafb0d1b1862119894c99b7edf190db3e；aip_task_store.py=7a3ba2feb62c4e810bb8c8918572b97c6a28099e132f44a454568602cde4a5d2。未修改原 observation 测试文件。

231-5/231-6 的可恢复执行和用户允许慢模型等待要求：不能把默认30秒步骤租约当作模型超时，也不能超时重新发起未知调用。已有 heartbeat_step 保留 fence/assignment CAS，但 CanonicalTaorRunner 尚无调用点。

## 文件及行为
- 新增 `services/aos-api/aos_api/aip_taor_lease_adapter.py`：包装既有适配器，调用前、等待每 lease_seconds/3、完成后通过既有 Owner 续租。每阶段仅提交一次调用；主线程续租，单个工作线程运行调用，各阶段串行。调用返回前不退出包装器，不遗留并行调用；续租失败等待原调用收尾后抛出安全的 Store 错误，不记录已成功步骤、不自行重试、不输出异常正文。
- 修改 `services/aos-api/aos_api/aip_taor_loop.py`：新增严格布尔 opt-in `renew_step_lease=False`；启用时 lease_seconds 必须正整数。仅在成功 claim 后包装，不引入第二执行引擎。显式注入 connect_factory 必须能供单个调用线程使用独立连接，不得跨线程共享事务。
- 修改 `services/aos-api/aos_api/aip_task_store.py::heartbeat_step`：保留 current fence/assignment 检查，追加运行/任务处于 running/executing 或 pausing/paused 的配对；取消/终态不再续租。合法暂停允许当前步骤达到安全检查点。
- 新增 `services/aos-api/tests/test_aip_taor_lease_adapter.py`，必要时提取既有 `test_aip_taor_observation_recovery.py` 的隔离运行创建 helper。验证超出1秒租约的单次1.4秒慢调用、丢失fence/续租错误、不重发、默认路径、真实PG取消及暂停。

## 边界及退出
本波仅本地开发测试，不调用Provider，不改主库，不启用生产worker。无法取消已发出的外部请求；失租后只等待其返回，Provider attempt原有持久记录由后续对账处理。数据库不可用或调用无限挂起不伪装成功；网络/Provider超时仍归原传输层。恢复结果仍受上一波原始观察哈希检查和 D03 当前来源核验。新增选项默认关闭，回退无需数据迁移。

退出：先红后绿、一次性完整克隆实际续租/暂停/取消验证、相关回归、方案一致性审查、证据和提交。下一波正式D03工作者谱系绑定并使用 opt-in。
