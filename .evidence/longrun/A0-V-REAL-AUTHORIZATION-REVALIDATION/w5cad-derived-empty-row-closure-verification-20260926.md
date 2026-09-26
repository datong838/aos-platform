# W5cad｜派生命令空记录关闭计数隔离核验（2026-09-26）

方案 `5b33a9f1` 先行；上位 231 A0-V/BG-00，W5c4z/W5c5a。原真实组与真实 Owner/迁移均未修改。

## 九步证据

1. 复习 231 串行 A0-V→A1、`ControlledIngressJournal.save_derived` 先验父记录与只允许合法 journal 的合同，以及 `a0v_091` 对 `ecommerce_ingress_derived_command` 的正式计数。W5cac 18/18 为隔离测试，不是业务授权。
2. 文件级范围仅测试 `services/aos-api/tests/extension_runtime/test_a0v_w5c4z_nonzero_effects_pg.py`、本方案和本 verification；生产代码/迁移零改动。
3. 原有“无 input/有 12 条空 input”两变体保留；第三变体在第一个合法空父记录后，经正式 `ControlledIngressJournal.save_derived(..., ())` 保存 **1 条派生 journal 行，命令数组 `[]`**。不构造非空商城行或 Dataset Receipt。
4. 三变体均通过故障注入：正式关闭 SQL 的 Receipt 写入后 Run UPDATE 故障使关闭事务回滚、12 Run 保持 running；撤故障后唯一调用返回 `businessAccepted=false`、12 Run failed，原效果行保留。新变体 `derivedCommandCount=1`，其他两变体为 0；数据库原行数同步核对。
5. 第一次定向有界运行 **3 passed，7 warnings，12.55s**，runner `CHILD_EXITED`、exit 0、21.443s；随后补 `commands == []` 断言并做最终相邻有界回归 **9 passed，16 skipped，7 warnings，14.43s**，runner `CHILD_EXITED`、exit 0、23.273s。16 skipped 来自旧 18432 专用夹具未设置 `AOS_EXTENSION_PG_TEST=1`，**不计通过**。测试专用 5433 PostgreSQL 中 `aos_test_%` 数据库残留 0。
6. 内置浏览器只读打开 `127.0.0.1:18181/docs`，Swagger `aos-api 0.3.0` / OAS 3.1、`/openapi.json` 可见；HTTP 200。8080 连接拒绝。浏览器只证明 HTTP-only 文档可见，不能验收业务路径；没有点 Authorize/执行按钮。
7. 代码和方案一致：只新增测试变体和断言，不改变旧两变体，`git diff --check` 通过。该行是**空命令的持久 journal 行**，因此本波只缩小 effect 计数/回滚覆盖债，不能证明非空业务输入、派生业务命令或 Dataset Receipt。Fleet 宇宙/旧入口撤权/Owner 绑定/独立历史原始行仍缺，原 12 Run 不关闭、不重跑；A0-V/BG-00 未通过。
8. 本 verification 与测试代码精确提交；随后将 AOS 上下文/Prime 受管记忆记为 W5cad no-authority，并读回。用户的两个 W5c8i 未跟踪文件保留不动。
9. 下一波：只读核对剩余外部门禁与可安全补证项；如果无可信 Fleet/原始行证明或正式不接受业务结果的退休选择，停止任何真实 effect，不制造授权。230 L0/dev-org 零 canary/m1 单写不 push 继续。
