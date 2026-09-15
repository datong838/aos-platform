# SC4-5l6g 主库 038→050 受控升级验证

日期：2026-09-15
方案提交：`fbd03c45`
执行器提交：`3f75c4c8`
目标：`colima-aos-extension / aos-a0v-recovery-pg / aos_meta_head`

## Rules 与执行范围

- 先写方案和退出条件，再编码；只允许 m1 与任务 `A0V-NATURAL-CHAIN-MAIN-UPGRADE-20260915`。
- 服务与 Runtime Host 在迁移期间保持关闭；不写经营业务、不读上游商城、不调用模型、不 push，230 L0 挂起。
- 固定 backup → clone restore → clone 038..050 → clone readback → apply intent → main 038..050 → independent readback；存在旧文件、克隆或 intent 时拒绝覆盖/重发。
- 迁移失败依赖事务回滚并保留诊断；成功后不做原地破坏性 downgrade。

## 基线与受保护恢复点

- 重启后恢复独立 Colima profile，`verify_environment.py` 通过；默认 Docker context 保持 `desktop-linux`，专用 daemon 保持 userns 隔离和无宿主目录挂载。
- 主库升级前为 `a0v_038`、532 张 public 表；正租户 dispatch=9、runtime binding=8 且 actionable=0、未停 schedule=0、claimed/unknown Outbox=0；canary dispatch=0。
- 0600 备份：`/Users/ddt/work/projects/ai_agent/.aos-recovery-20260915/state/natural-chain-main-upgrade/aos_meta_head-before-a0v_050.dump`，5,566,869 字节，SHA-256 `c80faf004b53c1975d7b1a1acae692fb27672a95fd275c4e4f62548ad7c0bde6`。
- 受保护 `prepare.json / apply-intent.json / apply.json` 已落同一仓外目录；执行器、十二迁移和备份哈希均被 proof 固定。

## 克隆与主库事实

- 从备份恢复唯一克隆 `aos_natural_chain_upgrade_20260915_test`，连续执行 `a0v_039..a0v_050`；独立进程 readback 为 revision 050、业务指纹一致、quiet boundary 一致。
- 主库在数据库 advisory lock、5 秒 lock timeout、120 秒 statement timeout 下执行同一十二步，Alembic逐步日志完整；未 stamp、跳步或降级。
- apply 后独立 `readback`：`NATURAL_CHAIN_MAIN_SCHEMA_DEPLOYED / a0v_050 / businessWrites=0`。
- 34 张关键既有业务表以逐行 canonical JSON 指纹比较，迁移前后完全一致；Outbox Delivery只排除本次新增且为空的两列后比较。正租户9路dispatch、8个不可执行binding、0未停schedule、0未决Outbox与canary=0均未改变。
- 八张新增事件/快照历史表均为空，强制RLS，运行角色只有SELECT/INSERT且无UPDATE/DELETE/TRUNCATE；均有不可变trigger。五个关键受控函数为runtime-only SECURITY DEFINER，PUBLIC无EXECUTE。事件策略配对约束、完整十路event-control group、双Receipt列/约束和runtime无Outbox直接UPDATE均通过。

## 验证

- 升级器纯合同：`6 passed / 0.06s`。
- 039–050 迁移、Store及执行器首轮：`46 passed / 38 explicit opt-in skipped / 12.18s`；跳过原因全部为 `dedicated database opt-in required`。
- 按要求开启独立PG opt-in后：Link/Retirement/Requirement lock `36 passed / 74.38s`；原生十二源Group Claim `4 passed / 5.27s`，无 skip。
- AR2 `verify_closure.py --phase ar2-7`：1956 scanned / 196 classified / 93 migrated；五类错误列表空。
- Prime：七个强一致投影 CURRENT，Codex eventual PENDING_ASYNC；validate GREEN，AOS-000573，1201 Delivery / 1184 Task / 2901 Event。

## 一致性、风险与下一项

- 与方案一致：此次只改变 schema 和受控函数/约束，不改变现有安装、路由、Task/Run、商城对象或交付状态。迁移器不能创建 ProductEvent、Case、Run、Requirement 或成功 Receipt。
- 主库已到代码 head，但两个历史安装仍 disabled/fenced/unknown，资源 released；这是真实安全基线，不是安装恢复成功。
- 下一步必须先核当前签名包是否与 HEAD/新自然链代码一致。若不一致，构建、签名、资格审查新领域候选，再通过原 Owner执行安装、配置、enable、disable/fence、Host重启恢复、卸载和重装；每一步按实际 Receipt对账，canary持续为零。

## 重启后控制面与页面入口恢复

- 代码基线 `2c9c8bdf`。`a0v_product_controlled_api.py check` 在主库 050 上再次通过：本地诊断元数据、Host Web 隔离探针、Runtime、目录及 UI 读取身份均指向 `aos_meta_head`，相互权限边界不变；`sourceCalls=0 / runsCreated=0`。
- 受控 API 以唯一 PID `32492` 监听 `127.0.0.1:18181`；启动日志明确 migration disabled、Runtime Host disabled、QYH Cron disabled、AIP logic automation disabled、模型健康维护 inactive、SSH 预热 disabled。`/v1/health` 与 `/v1/ready` 均为 200。
- 前端从 `apps/web` 正确根目录、固定 Node 与 `VITE_AOS_API_PROXY_TARGET=http://127.0.0.1:18181` 启动。PID `33540` 监听 5173，PID `33568` 监听 8434；两端 `/ontology` 和 `/api/v1/health` 均为 200。
- 首次前端尝试因重启后 PATH 无 Node 且包管理器依赖检查并发而失败；由该尝试产生的 `pnpm-lock.yaml` 变动已逐行还原，原有受保护 `package.json / package-lock.json` 差异未触碰。第二次从错误仓库根启动虽监听但 `/ontology` 为 404，核对准确 PID 后只停止本轮两个 Vite 进程，再从 `apps/web` 重启成功；两次失败均未接触主库或业务 Worker。
- 服务恢复后再次独立执行升级器 `readback`：`a0v_050 / businessWrites=0 / actionableBindings=0 / unresolvedOutbox=0 / unstoppedSchedules=0 / dispatchRoutes=9 / canaryDispatchRoutes=0`。QYH 恢复观察仍显示两个历史 generation 均 `enabled=false / operation_fence=true / observed_state=unknown`，全部三项资源 released。
- Runtime Host 本步有意保持关闭。现有签名根最高为 core 1.3、growth 1.7、Niushop 1.5；growth 1.7 虽声明八工作台和既有分析 API，但早于 039–050 与本轮自然 ProductEvent→DataRequirement Outbox→快照恢复逻辑，不能冒充当前完整领域包。下一波先形成当前代际构建、签名、资格审查与重装方案，再启动唯一 Host。
