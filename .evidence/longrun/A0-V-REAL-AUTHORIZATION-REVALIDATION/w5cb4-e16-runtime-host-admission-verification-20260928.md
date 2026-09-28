# W5CB4 E16：当前 Host／Owner 运行准备准入 verification（2026-09-28）

## 结论与边界

本波完成“受理回执不等于 Host 可执行”的前后端围栏：当前 Host task、精确租户 assignment、验证动作的安装 Owner 缺失或读失败时，运行准备／验证不可新受理；页面也禁入。已有同幂等键 Receipt 仍由原路径回读，未知结果在页面冻结重发。**这不是运行包已安装、八工作台可用或首条业务链已通过的证明。** 未读取商城源数据、未手工 `run_definition`、未重放旧 12 Run、未生成运行 operation、未删除卷或备份。

## 九步闭环

1. 上位复习：对照 231／231-3／231-9、栖月汇产品方案、E15 verification；目标仍是真实可安装、可配置、可禁入、可恢复的电商首链，不以按钮可点代替业务结果。
2. 文件级方案：`w5cb4-e16-runtime-host-admission-plan-20260928.md`，提交 `01fe64e2`；09:00 最新栈重启检查 `w5cb4-daily-latest-stack-20260928-0900.md`，提交 `bf4dee67`。实施范围为 RuntimeHost 当前 assignment 查询、router 进程准入／DTO、生命周期命令 handler 复核、前端精确状态禁入及相邻测试；不改数据迁移。
3. RED 与最小实现：先加入 Host inactive／task done／无 assignment／错租户与安装／verify Owner 缺失／只读失败／原幂等 Receipt 的失败用例，后实现。`request_preparation` 在原 `execute_idempotent` handler 内、operation `accept` 前复核；GET 的 `preparationExecutable` 仅为当前投影，POST 重新复核。前端要求当前安装 ID、revision、ETag 与运行视图吻合且字段严格为 `true`；未知结果只显示只读对账提示，不再给运行命令重发按钮。
4. 专项：最新运行 `test_runtime_host.py`、`test_lifecycle_service.py`、`test_runtime_installations_api.py`：62 passed，7 个既有 warning；无失败。
5. 累计：此前本波相邻后端集合 101 passed、43 skipped（需隔离 PG 的用例，不能视为通过）；前端全套 307 文件／2694 tests passed，TypeScript 检查、Vite build 通过。没有以 skip 代替真实数据库验收。
6. 浏览器：同一当前安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813` 为 approved、revision/ETag 3/3、active 无、runtime `not_prepared`、无 binding。重启前“准备运行资源”可点；最新代码重启后 `/apollo/assets` 显示“当前 Host 或租户 Owner 尚未核验为可执行”，按钮 disabled。仅只读查看，未点击运行提交。八工作台目录仍“暂无可见工作台入口”，电商业务登记服务暂不可用、八类配置候选缺失，列后续准入缺口。
7. 方案／代码一致性复审：服务端 status `ACTIVE`、Host task 存活、精确 scope assignment；`runtime-verify` 另查 exact Owner。任何异常返回 false。GET 与 POST 分离，客户端字段非授权令牌；安装状态、权限、revalidator、幂等 Receipt 既有检查保留。残余竞态：Host／Owner 可在准入读回与事务提交后变化，故 worker 的消费期检查仍必需；本波不声称原子化 Host 租约。未建立 Host 的当前运行环境因此保持拒绝。
8. 证据及数据面：09:00 前置备份为 `/Users/ddt/work/projects/ai_agent/.aos-daily-backup-20260928-zQG9WJ/aos_current_preview_20260927_a0v109_0900.dump`，`pg_restore -l` TOC 5499，但未独立全库恢复。代码变更后再次使用原 `aos-a0v-recovery-pg-data` 重启 PG／8080 API／8434 Web，migration disabled、Runtime Host0、worker0；健康／就绪／页面 200，18181 关闭。当前库 `aos_current_preview_20260927` migration `a0v_109`；重启后只读计数 `extension_runtime_operation=0`、`extension_runtime_binding=0`、`extension_runtime_host_assignment=0`。没有外部效果可重发。
9. 提交与下一波：本文件随 E16 代码精确提交到 m1；随后更新 AOS／Prime 上下文。E17 优先厘清当前签名 bundle root 与独立身份／目录／OCI 正式准入，使 Host 可在当前权威卷和真实配置下安全启动，再推进自然首链。不得用旧目录、假身份或高权限捷径制造绿色；缺失时继续可独立完成的产品配置／首链代码工作。

## 风险与明确未通过项

- 当前 `.env` 的 `AOS_BUNDLE_ROOT` 仍指向不存在的旧目录；当前签名回执不等于运行 Host 已加载。
- Runtime Host／assignment／Owner 均未正式就绪；无运行 operation／binding，八工作台和自然首链仍未验收。`dev-org/dev-project` 仅隔离 canary，不能用作正向业务结果。
- 本波服务端拒绝路径有自动化测试，浏览器仅验收只读禁入，没有为了测试而发真实运行命令；从当前状态创建 Host／Owner 需另波正式权威与许可链。
