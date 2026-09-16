# Y6b 主库受控升级与后续执行拓扑门

2026-09-16。仅在Y6a收口且clone/backup/五迁移/executor hash独立复核通过后实施。新增 scripts/a0v_snapshot_schedule_main_deploy.py 与对应 tests/test_snapshot_schedule_main_deploy.py（具体合同编码前补）；Y6a clone-only脚本保持不可升级main，不能去掉保护借用。

主库061→066为追加表/函数/约束，不更新旧业务行。使用原单迁移事务机制、明确source/target/五文件hash、current lease；同事务旧表摘要前后必须一致，七新表空且RLS/权限/触发器通过，提交后独立版本/模式读回。保留当前主库新一致性备份及原Y6a已恢复备份；任何不确定提交只读原intent/proof，不重新升级或stamp。禁止自动downgrade或从backup覆盖主库。

API61700、Host12960和旧业务任务保持运行状态，本波不启用新worker/不改变调度enabled/不读源。主库迁移通过不等于应用执行已部署。Y5d选择/控制/绑定审批及组定义仍待当前共同窗口。

Y6c部署拓扑门：现有独立 scripts/a0v_ecommerce_runtime_host.py 只有product-event和analysis-data两个业务worker；Y4的新snapshot worker在main.py应用生命周期中，并要求同进程host_task健康。当前受控API固定关闭host，不能直接打开snapshot开关，否则会fail closed；也不能启动第二Host。切换前必须形成确切的单Host方案，比较原main统一托管路径和独立Host扩展路径，明确stop/drain、Store生命周期、状态API观测和权限重核验，不靠临时手动Runtime调用作为经营接线。这个发现补入原计划，不以Y4隔离green掩盖部署缺口。

## 编码前合同细化

main_deploy独立加载原安装迁移事务实现，固定新TASK/STATE、SOURCE061/TARGET066/五文件和原clone验证函数。Y6a脚本和proof不改。validate_attestation纯函数要求exact outcome/source/target/main/clone、迁移和执行器hash、before非空且before==after、备份hash匹配；调用侧验证私有文件权限/无symlink、重新hash备份及clone原表/schema。再主库导出新一致性备份到本波private state，保留摘要和600文件。

apply仅固定aos_meta_head，无参数选择目标；先exclusive apply-intent，再原单事务upgrade，transaction-verified由原实现提交前冻结。readback核main066、七表权限与空表、原事务before==after/hash、intent一致，核新备份hash。任何已有intent只走readback，不自动重试升级。新main脚本hash纳入transaction/executor，克隆proof单独绑定原clone脚本hash；两者不同不是篡改，必须分别验证。测试篡改source/clone/hash/旧表摘要均拒绝，且main profile不影响clone-only保护。

## 验收

主库已通过原单事务061→066五迁移并独立读回；544旧表在事务内摘要前后相等，新七表为空且权限/租户/触发器一致。当前一致性备份及原clone恢复证明均保留。再次调用main脚本走已有intent readback，未重新迁移。API18181健康，Host未重启，源run11/claim10保持，enabled schedules=0。

新部署保护4项加clone2项共6 passed / 3.32s（/tmp/aos-y6b-final.log）；Red缺模块。私有transaction-verified.json/backup/apply-intent完整；公开结果y6b-main-migration-verification.json。未改变源控制窗口、未建立enabled组、未启用snapshot worker；不把schema ready作为经营首链完成。

下一波Y6c采用原main统一托管Host+三业务worker的方向细化，复用独立Host同一组文件锁实现互斥；先验证健康/实际线程排空和旧Host生命周期停止的影响，再受控切换。若现有生命周期stop会改变当前安装资源，则必须在切换方案明确原资源恢复，不得默认重启无副作用。Y5d和原业务Run处置仍待。
