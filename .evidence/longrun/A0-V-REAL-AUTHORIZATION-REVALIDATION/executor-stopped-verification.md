# 执行器退出事实验证

2026-09-11，基线66d11861，A0V-EXECUTOR-STOPPED-20260911。

execute_pipeline_once在结果收集后检查自身dispatch线程is_alive，返回executor_stopped；调度只将严格True持久化。a0v008字段NOT NULL DEFAULT false，历史记录不假设已退出。仍存活超时线程不能获得退出事实；未开始/未知异常保持缺证。当前没有自动重领。

新增断言修改前4失败；最终19专项通过，含真实线程正常/异常退出与阻塞超时、调度严格布尔值、隔离PG迁移历史默认false/NOT NULL/已有true拒绝downgrade。PG迁移测试使用最小隔离表，非public完整迁移或真实调度证明。diff-check通过，现有弃用警告未修。

边界：本地线程停止不代表外部未知请求没有副作用，后续重领仅限原持久输入、只读源及Receipt对账，并检查当前权限。public未迁移、API未重载。下一波原失败运行重领与失败事实保留；真实首链/八工作台未完成，不push，230 L0挂起。
