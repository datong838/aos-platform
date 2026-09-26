# W5cad｜派生命令空记录的隔离关闭计数补证方案

## 上位与边界

复习 231 串行 A0-V→A1、231-9 BG-00、W5c4z/W5c5a 的原 Owner 12 Run 隔离夹具、`ControlledIngressJournal.save_derived` 及 `a0v_091` 的 effectEvidence。W5cac 的 Schedule 18/18 只证明隔离测试，不授权真实组。原始 12 Run、Fleet/旧入口撤权/独立原始行证明仍是硬门；不得读取商城源、重发旧 attempt 或手工运行定义。230 L0 挂起，dev-org 只作零 canary，m1 单写、不 push。

## 文件级最小清单

- 修改 `services/aos-api/tests/extension_runtime/test_a0v_w5c4z_nonzero_effects_pg.py`：在现有两变体外增加一个 *with empty input + one empty derived row* 变体。使用正式 `ControlledIngressJournal.save_derived(..., ())`，仅在已保存的空父记录上写一条合法派生 journal 行。验证注入式 Run UPDATE 失败会整段回滚、正式 Receipt 的 `derivedCommandCount=1`、原行保留及 `businessAccepted=false`。不得把这条零命令记录描述为非空业务数据。
- 不修改生产代码、迁移、真实库配置或现有测试夹具的其他行为。
- 本目录新增 verification；只对精确 AOS 上下文与 Prime 受管投影作必要更新，不清理无关用户文件。

## 执行与停止

1. 本方案先落盘并提交。2. 静态检查新增参数和 journal 合同。3. 仅在 `colima-aos-a0v-test-only:5433` 自动新建的一次性 `aos_test_*` DB 跑定向测试，使用项目 `.venv`；失败不自动重复未知边界。4. 核对测试数据库无残留、18181 仍 HTTP-only、8080 离线。5. 做邻近专项和有界累计回归；若运行超预算，以未完成记录，不宣称 GREEN。6. 浏览器只做允许的只读可用性检查，真实业务验收仍不可做。7. 复审方案/代码/结论一致性。8. verification 落盘并提交，再更新上下文/Prime 记忆并读回。9. 若无新授权证据，下一波回到外部门禁及剩余可安全技术债，不制造实收或业务效果。

退出标准：隔离派生行的计数、回滚、保留有正式测试终态；真实 A0-V 状态严格不变。
