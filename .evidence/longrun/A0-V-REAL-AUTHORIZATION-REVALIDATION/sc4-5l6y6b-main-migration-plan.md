# Y6b 主库受控升级与后续执行拓扑门

2026-09-16。仅在Y6a收口且clone/backup/五迁移/executor hash独立复核通过后实施。新增 scripts/a0v_snapshot_schedule_main_deploy.py 与对应 tests/test_snapshot_schedule_main_deploy.py（具体合同编码前补）；Y6a clone-only脚本保持不可升级main，不能去掉保护借用。

主库061→066为追加表/函数/约束，不更新旧业务行。使用原单迁移事务机制、明确source/target/五文件hash、current lease；同事务旧表摘要前后必须一致，七新表空且RLS/权限/触发器通过，提交后独立版本/模式读回。保留当前主库新一致性备份及原Y6a已恢复备份；任何不确定提交只读原intent/proof，不重新升级或stamp。禁止自动downgrade或从backup覆盖主库。

API61700、Host12960和旧业务任务保持运行状态，本波不启用新worker/不改变调度enabled/不读源。主库迁移通过不等于应用执行已部署。Y5d选择/控制/绑定审批及组定义仍待当前共同窗口。

Y6c部署拓扑门：现有独立 scripts/a0v_ecommerce_runtime_host.py 只有product-event和analysis-data两个业务worker；Y4的新snapshot worker在main.py应用生命周期中，并要求同进程host_task健康。当前受控API固定关闭host，不能直接打开snapshot开关，否则会fail closed；也不能启动第二Host。切换前必须形成确切的单Host方案，比较原main统一托管路径和独立Host扩展路径，明确stop/drain、Store生命周期、状态API观测和权限重核验，不靠临时手动Runtime调用作为经营接线。这个发现补入原计划，不以Y4隔离green掩盖部署缺口。
