# SC4-5L6Y5F4 R 验证：数据源健康与 Policy9 自然窗口

## 结果

- 18181 已在 Q/R 工作树代码上受控重载；`/v1/health` 与 `/v1/ready` 均成功，独立 Runtime Host PID 87185 未停止，snapshot worker 为 independent/IDLE。
- 对保存的 `niushop-qyh` 配置执行一次 `information_schema` 目录探针：1994ms、302 表、未截断，目录哈希 `sha256:08dde1a43c9c6ad46a4a021da4b0eade7bd34aff73efa0ad0a28498196467892`，业务行读取数为 0。
- v2 authority 精确引用 L v1 selection revision 1、control revision 1、schedule binding revision 14；Policy9 精确引用 Policy8 Receipt。
- 首次 Policy9 enable 因错误沿用 Policy8 binding revision 1，被 CAS 原子拒绝。回查确认无 Receipt、无 Policy9 binding、schedule disabled，未重发原命令。
- 新 v3 approval/idempotency 以 Policy9 expected binding revision 0 成功创建 binding revision 1；route 仍为原十条、group revision 37，未执行 route expand。
- 第二自然观察目录独立，schedule 于 `2026-09-17 00:25 +08:00` 装备为 `0 * * * *`；装备时窗口内 runs/ingress/occurrence 均为 0，inflight/unresolved 和负租户 dispatch 均为 0。
- 没有人工 schedule run。下一步只观察 01:00 自然终态并立即禁用。

## 自测与一致性

- 源探针、安全错误码、Q/P 回归与自然窗口测试：88 passed。
- CAS 校正及第二观察器测试：6 passed。
- `py_compile` 与 `git diff --check` 通过。
- AR2 closure 校验器当前仍报告本波次外既存 hash/dynamic-reference 漂移；本波次没有修改清册哈希，也不把该结果写成 green。

## 风险边界

- 当前结论只证明真实连接健康、精确后继授权和自然窗口已装备；尚未证明 01:00 源读取、ingress、occurrence、Case/Run 或下游经营闭环成功。
- Policy9 有效至 `2026-09-17 01:48:23 +08:00`。若 01:00 没有唯一终态、终态不明或失败，则先禁用 schedule，再只读诊断；不会补发人工运行。
- 保持 m1 单写者、不 push、230 L0 挂起；未触碰已有 package、overall-progress、截图、插件及其他未提交文件。
