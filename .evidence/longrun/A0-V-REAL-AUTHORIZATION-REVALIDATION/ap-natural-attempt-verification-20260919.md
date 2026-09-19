# AP 自然 attempt 与失败冻结验证

## 结论

AP 由 qcursor 自然领取，未调用 `run_definition`。首笔 attempt
`93e2fc05-ebcb-46e1-8288-2bb0be32ae31` 在 348 秒后以
`RECOVERABLE_INGRESS_DEADLINE_EXCEEDED / IngressJournalConflict` 失败。停止 qcursor 生效前，调度器已领取第二笔
`434092c8-c519-440f-8822-5ecff74287b5`；进程停止后该笔在 revision 2 以
`ATTEMPT_LEASE_EXPIRED` 废弃。不存在第三笔 attempt。

失败边界的 12 个 Run 仍为 running，12 个 Dataset Receipt、1 个 relationship assessment、1 个 1168-link
command 均保持；retirement、link Store Receipt、`ecom_link`、Store outbox、projection pending 均为 0，
`dev-org/dev-project` canary 为 0。因此失败没有形成未知部分提交，也不授权重发。

## 根因

严格 link batch 修复提交 `b287ccbb` 的提交时间为 2026-09-19 13:44:56+08:00；执行 Store 的 Runtime Host
PID 59258 启动于 2026-09-19 09:22:00+08:00。Host 是常驻 Python 进程且不热重载，所以 AP 执行时仍使用修复前
的 `EcomConsistencyStore` 内存代码。13:47 启动的 qcursor 只负责自然调度，它加载新代码不代表 Store 执行 Host
已经加载新代码。

## 处置

1. qcursor LaunchAgent 已 bootout，18181 不再监听，阻断后续自然领取。
2. 新增只读 `a0v_ap_attempt_guard.py`，精确冻结 failed → abandoned 两笔 attempt、request hash、幂等 ordinal、
   12 Run、Store、路由、资源与 canary 边界；任何第三笔或身份漂移 fail-closed。
3. 新增只读 `a0v_ap_continuation_router.py`，失败链只路由正式 pause，不执行 definition、Store 或 successor。
4. `a0v_ap_saved_snapshot_recovery.py pause-failed` 已在零 Store 副作用边界把 definition rev62 enabled 转为
   rev63 disabled，结果为 `AP_SAVED_SNAPSHOT_FAILED_RECOVERY_PAUSED`，sourceReads=0。

## 验证

- AP guard/router/recovery 专项测试：24 passed。
- 浏览器只读验收：8434 `/ontology` 正常渲染 AOS v1.6.5、导航与缓存本体内容；页面明确显示 aos-api 不可达、
  当前离线且写队列为 0，符合 qcursor 主动停止后的预期状态；未执行页面写操作。
- 方案与代码复审：守护器只含 SELECT；续跑路由 `automaticAction=false`、`businessWrites=0`；暂停动作要求
  exact 两笔终态、12 Run 与零 Store 副作用后才允许 CAS transition。

## 下一波

正式退休 AP installation/generation，确认九条路由回 legacy、三项资源释放、无 pending/unknown；随后受控重载
Runtime Host 并核对其启动时间晚于 `b287ccbb`，再创建 direct successor。不得在 AP generation 上重试。
