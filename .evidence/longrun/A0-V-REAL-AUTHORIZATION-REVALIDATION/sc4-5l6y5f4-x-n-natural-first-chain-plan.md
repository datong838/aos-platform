# SC4-5L6Y5F4 X：N 自然商品事件首链恢复方案

日期：2026-09-17

## 目标与现状

W 已证明 N 可安装、可恢复且九条经营路由已原子接管。当前 Policy9 和全部 schedule binding 都 disabled，event-control 路由已移除；Host 只有 N 一个 live target。X 波建立 N 专属、限时、可撤销的 Policy10，自然等待 Cron 读取真实栖月汇商城数据，验证 `source → ingress → occurrence → Case/Run`，不调用人工 run，不手工造 Case。

## 固定顺序

1. N preflight：锁定 W resume Receipt、N active/ready binding revision6、三 live resource、九路 group42、Host 唯一 N target、canary0、inflight0；真实商城只做目录/新鲜度只读探针。
2. authority v4：SourceSelection、RuntimeControl 是按 installation/generation 隔离的资源，N 首次建立时 previousRef 必须为空；ScheduleBinding 是按 schedule 继承的资源，精确引用 L v2 revision15，生成当前 N 与新 90 分钟有效期；schedule 仍 disabled。
3. Policy10：精确引用 Policy9 Receipt，保留同一真实 Case 与 investigation profile，写入 disabled Policy10；Policy9 保持 retired/disabled。
4. event route：独立审批后从九路 group42 扩展 `ecommerce_growth_event_control` 到 group43；不得修改九条业务路由目标。
5. enable Policy10：独立审批、expectedBindingRevision=0，绑定 N generation/epoch3；不在此步启动 schedule。
6. natural window：只把已有 `sch-p02-qyh-controlled-20260913-v1` 设为 enabled，等待下一次 `0 * * * *` Cron。最多接受一个 run；失败、结果不明、超过窗口或出现第二个 run 时立即禁用。成功后继续等 occurrence/Case/Run，达到终态也立即禁用。
7. 终态复核：核对 source rows、ingress journal、occurrence、dispatch attempt、Case/Run、幂等水位、Host worker计数、预算/审批/租户隔离；本波禁止外部发布与人工评审自动批准。

## 文件范围

- `scripts/a0v_n_product_preflight.py`
- `scripts/a0v_n_product_window.py`
- `scripts/a0v_n_natural_product_event.py`
- 相应 `services/aos-api/tests/extension_runtime/` 测试与本目录证据。

## 停止条件

任一 W Receipt、N 身份、前序 authority/Policy ref、route group、Host target、数据源身份、预算、审批、canary 或幂等水位漂移即停止并保持 schedule disabled。自然 run 未知时只读原 run/receipt，不补发人工 run；模型慢可延长下游观察，但不能换 key 或绕过审批。

## v3 前序引用纠偏记录

首次 v3 `selection` 尝试把 L 的 SourceSelection revision2 当作 N 的前序，Owner 以 `selection predecessor is not current` 拒绝；事务回滚，数据库无 selection 写入。失败 intent 原样保留。复核 Owner 查询域后确认 SourceSelection 与 RuntimeControl 的 current revision 以 installation/generation 为边界，而 ScheduleBinding 以 schedule 为边界。恢复使用全新的 v4 intent/key：selection/control 不带 previousRef，binding 继续精确引用 L v2 revision15；不覆盖、不重放 v3 key。

自然窗口于 02:21 CST 武装。原观察器 2280 秒会在 02:59 左右先于 03:00 Cron 退出；在未发生 run/ingress 且不改变 schedule 的前提下停止该只读进程，将初始观察上限修正为 3300 秒后重启。最长 running 延展仍在 authority 03:49 到期前结束；不重新 arm、不创建第二 intent、不改变业务幂等键。

03:00 Cron 自然成功读取 65 行并形成唯一 ingress，但 worker 对同一候选返回无明细 `ValueError`，未写 occurrence。schedule 已立即禁用，原 run/ingress 保留。当前 worker 日志只输出异常类型，不能安全定位固定拒绝门；最小诊断改动仅为受控 ValueError/PermissionError 输出单行、限长错误文本，其他异常仍只输出类型。回归后重启同一 Host，并只在原 Policy10/authority 有效期内短暂启用原 schedule，让 discovery 恢复同一已提交 ingress；不得创建新 source run，观察到一次诊断结果或 occurrence 后立即禁用。该恢复仍沿原幂等键与未消费判断，不修改数据库状态冒充成功。
