# Live installation lifecycle owner 验证

日期：2026-09-12

## 结论

单 Installation 的异步 lifecycle owner 已实现并通过合同与邻接回归。它在同一
`PreparationConsumer`/`PreparedJob` 上依次消费 `runtime-apply`、`runtime-verify`、`enable`；没有
live job 时不进入控制阶段，验证返回失败或抛错时不进入 enable。调用方取消不会取消 owner 持有的
tick；停止先等待 tick，再调用原 preparation stop，因此沿用既有 OCI 清理和 live directory 撤销。

## 实测

- owner + live invocation + live directory：16 passed。
- 既有 runtime host：17 passed。
- 专用 18432 恢复后 preparation consumer PG：12 passed。
- 专用 18432 恢复后 owned control consumer PG：18 passed。
- 合计 63 passed；`git diff --check`、两文件 `py_compile` 通过。

第一次开启 PG opt-in 时，系统重启后 `aos-ar1c-pg` 仍为 exited，6 个 fixture 在连接
`127.0.0.1:18432` 前置阶段报 connection refused，另 6 个无 PG 用例通过。随后在既有
`colima-aos-extension` context 启动既有 `aos-ar1c-pg`，同两组测试从头串行全绿。该前置失败没有进入
业务断言，也没有写共享数据库。7 条框架 warning 和 pytest 退出后的 JDBC closed-stream 日志是既有
现象，exit code 为 0。

## 方案一致性与风险

- exact consumer 类型、固定阶段顺序、同 job/scope/connect、失败短路、串行 tick、取消/停止收敛均与
  方案一致。
- 本切片没有可信安装发现、owner factory 或 production host wiring；control-plane directory 启动后仍
  不会自动出现 job。
- 进程重启后的在途 preparation 必须先由既有 recovery 收敛；不能把旧 OCI session 重新认领为新
  owner。
- 1.4.0 未改变，真实栖月汇租户、Provider、外部发布和业务数据均未触发；本结果不构成 A0-V 或真实
  经营闭环完成证明。

## 下一波

实现可信、只读、有界的 Installation lifecycle assignment 目录与 owner factory：仅从当前租户目录和
待处理 runtime lifecycle outbox 发现 exact installation，先恢复再创建 owner；仍不接公开业务入口。
