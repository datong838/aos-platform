# CQ 配置接续受阻实例正式退休方案（2026-09-21）

## 当前权威

CQ installation `fff0b0d3-bf8f-44b0-b1b7-6a2972daeb80`、generation
`ae8a1005-99fb-48c5-9dfe-8f76590bc0c8`，安装 etag5、lock
`sha256:6b3debbfebb5b16297f35e2271944a8a9775b2c178922d31525655088f919b50`。策略续期后
configuration rev2 已通过正式 configure/enable 写入 Binding rev9/epoch5
`enabled/ready/unfenced`；九路仍指向 CQ epoch3 rev252/group279。definition rev193
disabled，CQ attempt=0，三资源 pending。十二 Run 与 Dataset Receipt 保留，Store Receipt、
link、projection pending 与 canary 均为零。唯一 Host PID 8784 在线。

配置 refresh 历史属于不同的旧 J activation，现有 Owner 与不可变触发器禁止跨
activation/installation/generation 续链；snapshot prepare 仍要求 Binding rev6/epoch3。
本波不修改历史模型、不绕过门禁，改走既定 fail-closed retirement + direct successor。

## 文件级清单与动作

1. 复用已验证 `scripts/a0v_as_failed_retirement.py`；AS 默认合同不变。
2. 新增 `scripts/a0v_cq_blocked_retirement.py`，固定 CQ identity、definition rev193、
   active Binding rev9/epoch5、九路 rev252/group279，attempts 必须严格为空。
3. 新增专项测试，锁定单次 disable、禁止 `run_definition`、不修改十二 Run。
4. 串行执行 `preflight → request-disable → process-disable → audit`。请求只经既有安装
   控制 Owner；处理先读回，未知结果不重发，只在 exact accepted 时由正式 consumer 或
   现有 Host 完成 fence/detach。
5. 终态要求 Binding rev11/epoch6 disabled/fenced/unknown、九路 legacy rev254/group281、
   三资源 released、definition rev193 disabled、attempt 仍为 0、全部保存快照与零副作用
   边界不变。随后 SIGTERM Host 8784。

## 退出条件

专项测试通过，四阶段 0600 私有结果完整，verification 落盘并精确提交。随后以 CQ exact
detach Receipt 为唯一父权威创建 CR direct successor；禁止复用 CQ generation、禁止手工
Store 重发、不 push，230 L0 继续挂起。
