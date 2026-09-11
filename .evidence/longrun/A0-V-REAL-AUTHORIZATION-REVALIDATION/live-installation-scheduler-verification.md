# Live installation scheduler 验证

日期：2026-09-12

## 结论

新增每 TenantScope 有界 `LiveInstallationScheduler`。每个 tick 从 pending-apply 目录创建尚未拥有的
Installation owner，并按 UUID 顺序 tick 全部 cache；descriptor 在 apply ACK 后消失不会停止已拥有
session。同 Installation 本进程只创建一次，cache 上限 100。

调用方取消不取消 scheduler tick。identity-bound revoke 等待 tick 后只停止 exact owner。host stop 先
等待 tick，再清空可见 cache 并逐个 stop；任一 cleanup 抛错仍会尝试其余 owner，最后保留首个错误。

## 实测

- scheduler/owner/directory/live directory/runtime host：44 passed。
- directory/preparation/owned control 真实 18432 PG：33 passed。
- 合计 77 passed；`py_compile`、`git diff --check` 通过。

测试覆盖一次创建、descriptor 消失后保留、UUID 顺序、上限/伪结果拒绝、owner 失败短路、并发拒绝、
取消收敛、identity revoke、stop 全量清理与 cleanup error。7 条既有 warning 和 JDBC 退出日志不改变
exit code 0。

## 一致性与剩余风险

- 实现与方案的保留、串行、上限、identity 和清理规则一致。
- scheduler 仍未进入 production assignment，且不能独立决定何时 disable。后续 host 必须固定顺序：
  recovery -> lifecycle scheduler -> configure -> revoke exact live owner -> disable。
- assignment revision 替换/删除时，现有 `RuntimeHost` 只停止当前 tick，不会自动 stop 被移除 assignment
  所拥有的 scheduler；下一波必须补 lifecycle diff 与 stop。
- 未组合正式 `PreparationWorker`，未启动 OCI，未改 1.4.0、真实租户或业务数据。

## 下一波

扩展 typed `RuntimeTenantAssignment` 与 `RuntimeHost` 生命周期：可选 exact scheduler 在 recovery 后运行；
assignment identity 被替换/删除或 host stop 时收敛旧 scheduler。disable 前的 per-installation revoke 需要
先补只读 disable target peek，不能在 scheduler 内猜测。
