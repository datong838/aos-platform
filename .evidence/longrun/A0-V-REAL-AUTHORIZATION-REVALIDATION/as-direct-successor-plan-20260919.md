# AS 直接后继、长续租观察与 saved snapshot 续接方案

## 上位 authority

AR 已由 disable operation `ffe632e9-3591-4dc9-b244-cdb12e5fcf00` 正式 detached；detach Receipt
`ed0229cc-9771-4f00-a210-4b2a8b7cf76b`，hash
`sha256:aaecdd9e8009ed6a0d633c78293c59109e75ddc2fb25509fe2424d71cd499f10`。九路由为 legacy
revision107/group134，三资源 released，definition rev67 disabled，AR 没有 execution attempt，Store 副作用为零。
Runtime Host PID 95647 已加载 commit `b57aaf93` 的有界健康重探修复，qcursor 保持停止。

## 文件级清单

1. `scripts/a0v_as_replacement_recovery.py`
   - 从 exact AR detach Receipt 创建唯一 AS installation；
   - 完成 approved → prepared → verified → staged → configured → enabled → observed。
2. `scripts/a0v_as_successor_business.py`
   - 消费 AS exact identity/config 与 AR detach Receipt，生成 registration-only 请求；预期 legacy group134。
3. `scripts/a0v_as_successor_cutover.py`
   - 经过 approve/prepare/pause/commit/validate/resume 切到 AS；预期完成后九路由 revision108/group135。
4. `scripts/a0v_as_saved_snapshot_recovery.py`
   - 从 rev67 disabled definition 迁移 frozen group，得到 rev68 disabled；
   - 以现存 recovery rev21 为前序，renew 生成 recovery rev22 与 enabled definition rev69；
   - `sourceReads=0`，不手工运行 definition。
5. 对应专项测试和终态证据。

## 长续租观察门

- AS enable 后先保持 definition disabled、qcursor stopped，不启动业务 attempt。
- 记录 runtime-apply operation 当前 revision；至少观察到 12 次新的 `runtime_lease_renewed`，覆盖约 12 分钟并超过 AR 在第 11 次续租失败的原时点。
- 观察期间 binding 必须持续 ready/enabled/unfenced，三资源 pending/unreleased，Host PID 95647 持续 ACTIVE，`dev-org` canary=0。
- 任何 Host 重启、健康过期、资源释放、route/binding 漂移均停止进入 Store，先按正式退休路径处理。

## 执行与停止规则

每一阶段使用不可变 intent、Receipt/hash、revision 和 tenant canary 做 CAS；已有 intent 时只 inspect，不重发。
不得手工 `run_definition`，不得恢复 qcursor，直到 AS 完成长续租观察与 saved recovery enable。任何未知结果禁止重发。

本波完成条件：AS active/ready、九路由指向 AS、连续续租门通过、definition rev69 enabled/recovery rev22 current、12 个
frozen Run 与 Dataset Receipt 保留、sourceReads=0。下一波才恢复 qcursor，观察唯一 AS 自然 attempt。
