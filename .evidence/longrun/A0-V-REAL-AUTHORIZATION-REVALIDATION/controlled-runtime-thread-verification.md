# 受控执行线程装配验证

2026-09-13；基线 m1 b2d2e507；沿用主 A0-V Lease。

新增 pipeline_controlled_runtime.py，固定服务器持有的服务、计划关联及恢复模式。独立 runtime DSN 构造 ConsistencyStore，在线程内开关资源，不能因调用方超时而提前关闭执行器。runtime_connections.py 提取原有 DSN 选择逻辑，保留文件权限验证和禁止 web 身份回退。phase5_pipeline_engine.py 接受 exact ControlledScheduleExecution，复用预检、工作线程、取消、证据引用验证和实际 stopped 判断。未传对象仍用原执行器。

验证：新增线程测试先 RED（入口缺少 controlled_execution 参数），实现后针对性和扩展组合 90 passed / 7 failed（97 项）。7 个失败均在 test_phase5_regression.py：4 个种子目录非空断言、模型目录非空断言、widget/theme 缺 meta_workspace 外键。以 git show b2d2e507 的原 phase5_pipeline_engine.py 在独立 Python 进程加载并单跑该文件，20 passed / 同样 7 failed；不改动基线文件或客户数据库。当前新增运行测试12项、连接测试21项与原 Pipeline 测试均在上述组合通过。新增超时反例验证线程仍运行时 executor_stopped=false 且资源未关闭，释放后退出；禁用模式不打开资源。装配测试使用显式假执行，不是实际源执行。

ar2-7 closure：1806 Python modules，158 classified，93 migrated，五组错误均为空。git diff --check 通过。

边界：main 仍 a0v_024，代码 a0v_025 未部署。API 未重新加载；P01 未启用或调用真实源。本切片的 validate_current/claim_recovery 服务方法仍需正式入口与 PG 联合覆盖；不得宣称经营首链完成。下一波：读取不可变计划关联，接 manual/recovery/cron，保证有绑定而服务不可用时不回退旧入口；随后025备份恢复部署和实际入口验收。
