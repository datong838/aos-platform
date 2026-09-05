# AR1-c 内部切片检查点（非 Delivery）

2026-09-05，authority AOS-000510，开发基线 m1@46e3da87；AR1-C-LIFECYCLE-PERSISTENCE Lease 仍在进行。AR1-c 未完成，不推进业务进度或称装卸已工作。

## 当前实现与实测

- 新增八表 additive 迁移，仅在专用引擎的临时 PostgreSQL 18432 执行；未迁移已有共享库。
- 运行操作幂等先于 ETag CAS，事件/outbox 同事务；安装 ETag 与事实/active revision 分开。
- 真实旧 Registry/Installation 五项迁移及旧 Store 创建 draft，与新从属操作兼容；不代表整个旧迁移链全部验收。
- 注册制品联合验证签名、精确 lock、image index、依赖锁、SBOM 与本地镜像。尚未接入正式生命周期最终事务。
- 一次性资源领取先提交后 OCI；双独立连接仅一个领取成功，回滚可重领；领取后重启只对账，不重复创建。
- fence 同事务关闭入口、递增 epoch、更新阶段及事件；旧 CAS 不重复递增。
- 数据库准入拒绝当前/登录角色及其特权成员角色，拒绝无租户、owner 和未 FORCE RLS 表；不提供任意 SQL 端口。
- 独立 Prime 增量复核发现 BYPASSRLS 成员遗漏，已修正并补真实 PG 反证。

## 最后一次累计结果

238 passed，6 个既有 Pydantic warnings，26.88 秒，pytest exit 0。包括 8 项实际 OCI 测试。退出仍有既有 JDBC 空缓存日志 closed stream 错误，不称无告警。

此后新增 `release_revalidation.py`，在最终事务内重新读取 Registry/策略，不复用准备阶段结果；其专项加旧 runtime 拒绝路径 5 passed、6 warnings、6.72 秒。该增量尚未重新包含于上述 238 项累计结果，且尚未接入正式服务，不将两个计数相加冒充新累计验收。

命令：`AOS_EXTENSION_OCI_TEST=1 AOS_EXTENSION_PG_TEST=1 PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest --noconftest services/aos-api/tests/extension_runtime services/aos-api/tests/asset_registry/test_manifest_contracts.py services/aos-api/tests/asset_registry/test_manifest_loader.py services/aos-api/tests/asset_registry/test_signature.py services/aos-api/tests/asset_registry/test_installation_service.py services/aos-api/tests/asset_registry/test_installation_revalidation.py services/aos-api/tests/asset_registry/test_release_policy.py services/aos-api/tests/asset_registry/test_canonical_hash.py -q`

本段无页面修改，浏览器 N/A；不冒充后续 AR1-d 页面验收。没有新业务闭环、Provider 调用、真实业务数据写入或发布。

## 接续顺序

最终内部检查点：以上增量加 `test_control_wiring.py` 累计 **255 passed、6 warnings、35.78秒**；独立 Prime 确认失败收敛及独立工厂无新增确定缺陷，可以保存内部代码检查点。`build_installation_service` 保持旧默认，只有新工厂显式配置 planning validator；不宣称上游浏览器入口已贯通。AR1-c Lease继续ACTIVE，不写整波Delivery、不改已完成业务场景数。

本次接续增量：`lifecycle_service.py` 已连接既有 CommandReceipt/Installation Store，准备请求仅202，不激活；TI6实际角色路径已验证，新表权限来自迁移，测试没有额外授予新表权限。`planning_revalidator` 只用于submit/approve，旧apply执行门保留。角色/准备/OCI清理ID修改后的累计250 passed、6 warnings、27.93秒；随后资源清理观察专项18 passed、6 warnings、8.35秒，尚未在这次250累计内。清理unknown→released保留操作needs_attention，不能把资源回收事实当整操作成功。独立Prime第二轮接线发现（角色授权、上游规划入口）已实施修正，待末次回读。

继续 AR1-c 正式服务：当前安装批准与权限重验、持久资源观察/未知结果恢复、最终安装 CAS；再补签名查询模板与受限角色执行、schema/audit 保留合同及故障验证。仅原语测试不能关闭这些任务。完成整波专项/累计/Prime/Delivery 后才能进入 AR1-d API/UI，随后 AR2→A0-V→A1。
